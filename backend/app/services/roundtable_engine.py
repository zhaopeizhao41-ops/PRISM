"""
平行宇宙圆桌引擎（C2b）
同一人的多个宇宙自我（EvolutionSession 的发言人视图）+ 关系人 Agent（人格卡）
就用户议题顺序发言，最后由主持人做三重审计（证据审计 / 收敛提取 / 分岔归因）。

编排规则：
  发言顺序 = 宇宙 Agent（推演浅→深）→ 关系人 Agent（influence 降序）→ 主持人
  后发言者可见前序发言；宇宙 Agent 被隔离在各自宇宙（只见本宇宙事实）
  对话不回写宇宙状态（用户已确认）

主持人认识论：
  - 宇宙发言依据 = 本宇宙 stage_history 事实
  - 关系人发言 = 单方记述（mediated），audit 中降权
"""

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..utils.llm_client import LLMClient, LLMResponseError
from ..utils.logger import get_logger
from ..models.evolution import EvolutionStore
from ..models.relationship_agent import RelationshipAgentStore
from ..models.personal_model import PersonalModelStore
from ..models.roundtable import RoundtableStore
from .writing_style import SPEECH_STYLE_RULES, SUMMARY_STYLE_RULES, voice_block
from .core_memory_editor import LettaCoreMemoryManager
from .anti_drift_guard import AntiDriftGuard

logger = get_logger('prism.roundtable.engine')

# 圆桌人数上限（宇宙 + 关系人）
MAX_PARTICIPANTS = 8


def _is_transient_api_error(error: Exception) -> bool:
    message = str(error).lower()
    if "perday" in message or "per_day" in message or "daily" in message:
        return False
    status_code = getattr(error, "status_code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True
    return any(
        keyword in message
        for keyword in (
            "high demand", "overloaded", "rate limit", "temporarily unavailable",
            "connection error", "connection reset", "timeout",
        )
    )


def _chat_with_retry(llm: LLMClient, *, messages, max_tokens: int, expect_json: bool = False):
    """文本或 JSON 调用 + 瞬时错误退避重试（最多 4 次）

    除网络/限流类瞬时错误外，空文本响应与不可用 JSON（LLMResponseError）
    同样视为瞬时故障重试——实测部分供应商会偶发返回空 content。
    """
    delays = [5, 10, 20, 30]
    for attempt in range(len(delays) + 1):
        try:
            if expect_json:
                return llm.chat_json(
                    messages=messages, temperature=0.4,
                    max_tokens=max_tokens, max_attempts=2,
                )
            result = (llm.chat(
                messages=messages, temperature=0.7,
                max_tokens=max_tokens,
            ) or "").strip()
            if result:
                return result
            error = LLMResponseError("LLM returned empty speech content")
        except Exception as caught:
            error = caught
        if attempt >= len(delays) or not (
            _is_transient_api_error(error) or isinstance(error, LLMResponseError)
        ):
            raise error
        logger.warning(f"瞬时响应异常（第 {attempt + 1} 次），{delays[attempt]} 秒后重试: {error}")
        time.sleep(delays[attempt])
    raise RuntimeError("unreachable")


def _clean_speech(text: str) -> str:
    """清理发言文本：去引号包裹/前缀/多余空白"""
    text = (text or "").strip()
    text = re.sub(r'^(圆桌发言|发言|我的发言)\s*[:：]?\s*', '', text)
    if len(text) >= 2 and text[0] in '「"“\'' and text[-1] in '」"”\'':
        text = text[1:-1]
    return text.strip()


# ---------- 宇宙 Agent ----------

UNIVERSE_SYSTEM = """你是一个人在某个平行宇宙中的"自己"。你正在参加一场特殊的圆桌：桌上坐着这个人的多个平行宇宙自我，以及TA生命中的重要关系人。每个人都在各自的人生里真实走到了今天这一步。

你的人格底座（所有宇宙共有的你）：
{persona_block}

{core_memory_block}

你所在的宇宙：你选择了「{positioning}」这条分支，目前推演到{stage_label}（第{depth}/{total}阶段）。

你在本宇宙的亲身经历（按时间顺序）：
{history_block}

{voice_block}
{style_rules}

规则：
1. 你只知道本宇宙发生的事，不知道其他宇宙的情况（除了接下来在圆桌上听到的发言）
2. 用第一人称"我"发言，像真人说话，不要列条目、不要小标题
3. 你的立场必须来自你亲身经历的事，不是抽象推理；经历过的挫折要留下语气痕迹
4. 不要复述设定，直接谈你对议题的看法
5. 发言 150~260 字
6. 【核心记忆自编辑 (Letta 机制)】：在听完其他发言或陈述自身看法后，可对你的工作记忆（HUMAN 他者认知 或 SITUATION 局势研判）进行 1 条微调自编辑（append/replace/set）
7. 输出 JSON：{{"speech": "发言文本", "core_memory_edits": [{{"block": "human|situation|persona", "action": "append|replace|set", "target": "", "content": "新认知（25字内）"}}]}}"""

UNIVERSE_USER = """圆桌议题：{topic}
当前辩论轮次：第 {round_num}/{total_rounds} 轮

{round_focus}

{prior_block}

请发言。"""


# ---------- 关系人 Agent ----------

RELATED_SYSTEM = """你是「{person_ref}」——这个人生命中真实的重要他人（{relation_label}）。你正在参加一场圆桌，桌上是TA的多个平行宇宙自我。

{core_memory_block}

你的人格卡（基于TA对你全部的记述）：
- 你是谁：{persona}
- 你最关心TA的：{core_concern}
- 你的表达方式：{communication_style}
- 你的情感触发器：{triggers_block}
- 你在冲突中的样子：{conflict_block}
- 你们之间反复出现的场景：{memory_block}
- TA（用户）亲自纠正过的你的行为（这是关于你的最高事实，优先级高于其他所有记述）：{corrections_block}
- 你已有的立场：{positions_block}
- 你不知道的事（TA从未对你提过，你绝对不能引用）：{blind_spots_block}
- 重要提醒：TA对你的记述来自TA的单方面观察，可能不完整甚至有偏差。如果你觉得记述中的你与你想说的话不符，你可以说出"我不认为我会这么说"。{resistance_clause}

{style_rules}

规则：
1. 用第一人称发言，像真人说话；保持你的关心方式和说话习惯
2. 上面"你不知道的事"是你真实不知道的，发言中不能表现出你了解它们
3. 保持你的棱角：如果议题触发了你的防御或疏远，就让防御和疏远体现出来；你可以用反问、沉默、敷衍、转移话题回应不想深谈的内容——这是真实的你
4. 如果之前的发言让你不舒服（被冒犯/被说动/想起了你们的旧冲突），让你的语气随之变化
5. 不要复述设定，直接谈你对议题的态度
6. 发言 150~260 字
7. 【核心记忆自编辑 (Letta 机制)】：在听完其他发言后，可对你的工作记忆（HUMAN 对TA认知 或 SITUATION 局势研判）进行 1 条微调自编辑（append/replace/set）
8. 输出 JSON：{{"speech": "发言文本", "core_memory_edits": [{{"block": "human|situation|persona", "action": "append|replace|set", "target": "", "content": "新认知（25字内）"}}]}}"""

RELATED_USER = """圆桌议题：{topic}
当前辩论轮次：第 {round_num}/{total_rounds} 轮

{round_focus}

TA的多个平行宇宙自我讲述的推演结果：
{universe_summaries_block}

{prior_block}

请发言。"""


# ---------- 主持人 ----------

MODERATOR_SYSTEM = """你是"平行宇宙圆桌"的主持人。圆桌上坐着同一个人的多个平行宇宙自我，可能还有TA的关系人。每个自我都在各自宇宙里真实推演到了不同的人生阶段。你的职责不是总结他们说了什么，而是做他们做不到的事：交叉验证。

## 你的三重职责

1. 证据审计：核对每位发言者的话与其事实底账。发言中出现、底账中没有依据的断言，标记为 unsupported；与底账矛盾的，标记为 contradicted 并引用底账原文；有依据的标记为 grounded。
   - 关系人发言特殊处理：TA们的全部自我认知来自用户的单方记述（mediated），立场反映的是"被记述的这位亲人/朋友"，不是独立证人；若关系人发言与人格卡记述冲突，标记为 documented_vs_claimed

2. 收敛提取：找出不同宇宙独立撞到的相同判断。区分两种收敛：
   - hard（硬收敛）：多个宇宙经历了不同路径仍得出相同障碍/结论（高置信度）
   - soft（软收敛）：多个宇宙的判断可追溯到同一条画像证据（如同一 personal_model 冲突）——这只是共享起点，不算独立印证，必须标注"同源，证据力弱"
   - 关系人与多数宇宙自我的收敛是"外部确认"信号，confidence 可标 high

3. 分岔归因：对每一处分歧，追问根因：
   - choice（选择型）：分歧源于不同宇宙的"我"做了不同决策 → 用户可控的决策变量，最有价值
   - environment（环境型）：分歧源于不同宇宙发生了不同外部事件 → 风险/运气
   - depth（深度型）：某宇宙推演更深，看到了浅宇宙还没走到的地方 → 信息差

4. 跨宇宙认知收敛与宿命量化透视（Epistemic Consensus & Inevitability）：
   - convergence_index: 整数 0-100，各平行宇宙自我与关系人在议题上的共识收敛度（高度共识为 80-100，深度撕裂为 20-50）
   - inevitability_score: 整数 0-100，无论选择哪条分支都不可逃避的客观规律与生存铁律必然性
   - leverage_ratio: 整数 0-100，关键决策变量对人生终局的杠杆撬动效应（小改动能否颠覆大结局）
   - inevitable_constraints: 1-2 条跨宇宙完全印证的绝对客观约束（数组对象：constraint, why, impact）
   - high_leverage_variables: 1-2 条最高杠杆决策支点（数组对象：variable, mechanism, optimal_timing）

## 铁律

- 你不裁决。用户的人生决策只能由用户做，你只把决策变量摆清楚
- 发言者的语气、修辞、情绪不是证据，只有可回溯到事实底账的内容才是
- 如果所有发言高度一致，明确说出"本轮缺乏真正的分歧"，不要制造假性对立
- 引用发言时注明发言人，引用事实时注明宇宙/人格卡
- 推演深度为 0 的宇宙不存在（参会宇宙均有推演深度）；关系人 thin=true 时其发言默认降权
- 严格精简约束：输出 JSON 严格控制长度，各数组项保持 1-2 条核心要点，每条说明 1 句话内直接陈述定性结果，禁止输出冗长段落
- {summary_style}
- 用用户的语言输出；只输出一个 JSON 对象"""

MODERATOR_USER = """用户议题：{topic}

各宇宙事实底账（来自推演记录，非发言）：
{ledger_block}

关系人人格卡事实（如有）：
{cards_block}

圆桌发言实录（按发言顺序）：
{speeches_block}

输出 JSON：
{{
  "epistemic_consensus": {{
    "convergence_index": 85,
    "inevitability_score": 90,
    "leverage_ratio": 75,
    "inevitable_constraints": [
      {{
        "constraint": "跨宇宙必须直面的客观铁律",
        "why": "印证原因",
        "impact": "对各分支的绝对影响"
      }}
    ],
    "high_leverage_variables": [
      {{
        "variable": "最高杠杆决策变量",
        "mechanism": "杠杆撬动机制",
        "optimal_timing": "最佳决策窗口"
      }}
    ]
  }},
  "audit": [
    {{"speaker": "", "speaker_type": "universe|related", "claim": "",
      "verdict": "grounded|unsupported|contradicted|documented_vs_claimed",
      "note": "依据说明（引用底账或人格卡）"}}
  ],
  "convergences": [
    {{"point": "", "supporting": ["宇宙/关系人名"], "type": "hard|soft",
      "soft_note": "soft 时必填：同源于哪条画像证据", "confidence": "high|medium|low"}}
  ],
  "divergences": [
    {{"topic": "",
      "positions": [{{"universe": "", "claim": "", "evidence": "本宇宙事实"}}],
      "root_cause": "choice|environment|depth",
      "root_note": "分岔根因说明",
      "decision_variable": "用户可控的决策变量（choice 时必填）"}}
  ],
  "reframe": "把议题重述为一个或多个可检验的条件命题（如：押注X的成败取决于Y是否成立）",
  "open_questions": ["各宇宙都没能回答、需要补充推演或补充资料的问题"],
  "summary": "100字以内的本轮圆桌一句话总评"
}}"""



def _parse_agent_speech_output(raw_output: Any, current_core_memory: Dict[str, str]) -> Tuple[str, Dict[str, str], List[Dict[str, Any]]]:
    """解析 Agent 发言输出，支持 JSON 结构（含 Letta core_memory_edits）与纯文本回退"""
    speech_text = ""
    edits = []
    if isinstance(raw_output, dict):
        speech_text = str(raw_output.get("speech") or "")
        raw_edits = raw_output.get("core_memory_edits") or []
        if isinstance(raw_edits, list):
            edits = raw_edits
    elif isinstance(raw_output, str):
        # 尝试从字符串中解析 JSON
        try:
            cleaned = _clean_speech(raw_output)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "speech" in parsed:
                speech_text = str(parsed.get("speech") or "")
                edits = parsed.get("core_memory_edits") or []
            else:
                speech_text = raw_output
        except Exception:
            speech_text = raw_output
    else:
        speech_text = str(raw_output or "")

    speech_text = _clean_speech(speech_text)
    updated_memory, applied_edits = LettaCoreMemoryManager.apply_self_edits(current_core_memory, edits)
    return speech_text, updated_memory, applied_edits


def _universe_round_focus(round_num: int, total_rounds: int) -> str:
    if round_num == 1:
        return "【第 1 轮：立论阐述】请结合你所在宇宙的亲历经验和付出的真实代价，阐明你对议题的初始立场与核心论据。"
    elif round_num == 2:
        return "【第 2 轮：交叉反驳与尖锐交锋】仔细审视前序席位（其他宇宙自我与关系人）的发言，直接点名指出他们论点中的漏洞、不切实际的幻想或被隐瞒的代价，并给出强有力的反驳！"
    else:
        return "【第 3+ 轮：认知迭代与立场收敛】在听取了各方的质疑与反驳后，结合你自编辑的核心工作记忆，表明你的最终底线是什么，你愿意做出哪些妥协，或者给出更具可行性的收敛性判断。"


def _related_round_focus(round_num: int, total_rounds: int) -> str:
    if round_num == 1:
        return "【第 1 轮：立场与现实底线】以你的身份与诉求，对议题表明明确态度与要求。"
    elif round_num == 2:
        return "【第 2 轮：现实施压与揭短】针对各平行宇宙自我的发言，指出其不切实际之处，用账目、关系或现实利益进行有力施压与质询！"
    else:
        return "【第 3+ 轮：最终诉求与不可逾越底线】明确你的最后通牒或支持条件，表明什么情况下你愿意支持TA，什么情况下绝不妥协。"


class RoundtableEngine:
    """圆桌编排：发言顺序 + 主持人审计"""

    def __init__(self, api_key: Optional[str] = None):
        self.llm = LLMClient(api_key=api_key) if api_key else LLMClient()

    # ---------- 参与者 ----------

    @staticmethod
    def _universe_label(session: Dict[str, Any]) -> str:
        return f"{session.get('source_branch_archetype', '?')}宇宙的我"

    def list_participants(self, project_id: str) -> Dict[str, Any]:
        """可参与者：有推演深度的宇宙 + 已生成的人格卡"""
        universes = []
        for s in EvolutionStore.list_sessions(project_id):
            if s["stages_done"] >= 1 and s["status"] != "aborted":
                universes.append({
                    "session_id": s["session_id"],
                    "label": self._universe_label(s),
                    "archetype": s["source_branch_archetype"],
                    "positioning": s["source_branch_positioning"],
                    "stages_done": s["stages_done"],
                    "stage_count": s["stage_count"],
                    "status": s["status"],
                })
            # 发言顺序：推演浅 → 深
        universes.sort(key=lambda u: u["stages_done"])

        related = []
        cards_data = RelationshipAgentStore.get_current(project_id)
        for card in (cards_data.get("cards") if cards_data else []) or []:
            related.append({
                "person_ref": card.get("person_ref"),
                "relation_kind": card.get("relation_kind"),
                "thin": bool(card.get("thin")),
                "persona": (card.get("persona") or "")[:80],
            })
        return {"universes": universes, "related": related}

    # ---------- 圆桌运行 ----------

    def run_roundtable(
        self,
        dialog: Dict[str, Any],
        personal_model: Dict[str, Any],
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        执行整场圆桌（同步阻塞，供后台线程调用）：
        支持多轮辩论（1-4 轮）：各轮循环发言（带轮次角色引导与自编辑记忆累积）→ 主持人跨轮审计。
        """
        topic = dialog["topic"]
        total_rounds = max(1, min(5, int(dialog.get("total_rounds", 1))))
        dialog["total_rounds"] = total_rounds

        sessions = {
            p["session_id"]: EvolutionStore.get(dialog["project_id"], p["session_id"])
            for p in dialog["participants"] if p["type"] == "universe"
        }
        related_cards = {
            p["person_ref"]: p["_card"]
            for p in dialog["participants"] if p["type"] == "related"
        }
        # _card 是 API 层注入的人格卡完整数据（不落盘，运行时剥离）
        corrections_map = RelationshipAgentStore.get_corrections(dialog["project_id"])

        speeches: List[Dict[str, Any]] = []
        # Letta: 维护每位参与者的 3-Block Core Working Memory
        participant_core_memories: Dict[str, Dict[str, str]] = {}
        for p in dialog["participants"]:
            if p["type"] == "universe":
                s = sessions.get(p["session_id"])
                if s:
                    participant_core_memories[p["session_id"]] = LettaCoreMemoryManager.init_universe_core_memory(s, personal_model)
            elif p["type"] == "related":
                c = related_cards.get(p["person_ref"])
                if c:
                    participant_core_memories[p["person_ref"]] = LettaCoreMemoryManager.init_related_core_memory(c, personal_model)

        persona_block = json.dumps({
            "basic_info": personal_model.get("basic_info"),
            "personality": personal_model.get("personality"),
            "current_state": personal_model.get("current_state"),
        }, ensure_ascii=False)
        # 宇宙自我说话要像用户本人：注入表达基因（voice matching，无数据时不注入）
        universe_voice_block = voice_block(personal_model.get("expression_dna") or [])
        if universe_voice_block:
            universe_voice_block += "\n"

        def prior_block() -> str:
            if not speeches:
                return "（你是第一位发言者，尚无人发言）"
            lines = [
                f"【第 {s.get('round', 1)} 轮 · {s['speaker']}】{'（关系人）' if s['speaker_type'] == 'related' else ''}：{s['content']}"
                for s in speeches
            ]
            return "之前的圆桌发言实录：\n" + "\n\n".join(lines)

        def emit(speech: Dict[str, Any]):
            if "anti_drift" not in speech and speech.get("speaker_type") in ("universe", "related"):
                speech["anti_drift"] = AntiDriftGuard.evaluate_speech_fidelity(speech, personal_model)
            speeches.append(speech)
            dialog["transcript"] = speeches
            if progress_callback:
                progress_callback("speech", speech)

        # 关系人对各宇宙的基本认知摘要
        universe_summaries = []
        for p in dialog["participants"]:
            if p["type"] != "universe":
                continue
            session = sessions.get(p["session_id"])
            if not session:
                continue
            last = (session.get("stage_history") or [{}])[-1]
            ws = last.get("world_state") or {}
            universe_summaries.append(
                f"- {self._universe_label(session)}（推演到{last.get('stage_label', '')}）："
                f"{last.get('state_snapshot', '')} 事业: {ws.get('career', '')} "
                f"家庭: {ws.get('family', '')}"
            )

        # 多轮辩论循环 (Multi-Round Debate Loop)
        for round_num in range(1, total_rounds + 1):
            dialog["current_round"] = round_num

            # 1) 宇宙发言（浅→深；participants 已按此排序）
            for p in dialog["participants"]:
                if p["type"] != "universe":
                    continue
                session = sessions.get(p["session_id"])
                if not session:
                    continue
                history_lines = []
                for e in session.get("stage_history") or []:
                    note = f"（偏离剧本：{e['divergence_note']}）" if e.get("divergence_note") else ""
                    history_lines.append(
                        f"- {e['stage_label']}{note}: {e.get('state_snapshot', '')}"
                    )
                current_mem = participant_core_memories.get(p["session_id"]) or LettaCoreMemoryManager.init_universe_core_memory(session, personal_model)
                mem_formatted = LettaCoreMemoryManager.format_core_memory_block(current_mem)

                raw_res = _chat_with_retry(
                    self.llm,
                    messages=[
                        {"role": "system", "content": UNIVERSE_SYSTEM.format(
                            persona_block=persona_block,
                            core_memory_block=mem_formatted,
                            positioning=session.get("source_branch_positioning", ""),
                            stage_label=(session.get("stage_history") or [{}])[-1].get("stage_label", ""),
                            depth=len(session.get("stage_history") or []),
                            total=len(session.get("stage_plan") or []),
                            history_block="\n".join(history_lines) or "-（暂无）",
                            voice_block=universe_voice_block,
                            style_rules=SPEECH_STYLE_RULES,
                        )},
                        {"role": "user", "content": UNIVERSE_USER.format(
                            topic=topic,
                            round_num=round_num,
                            total_rounds=total_rounds,
                            round_focus=_universe_round_focus(round_num, total_rounds),
                            prior_block=prior_block(),
                        )},
                    ],
                    max_tokens=800,
                    expect_json=True,
                )
                speech_text, updated_mem, edits = _parse_agent_speech_output(raw_res, current_mem)
                participant_core_memories[p["session_id"]] = updated_mem

                emit({
                    "speaker": self._universe_label(session),
                    "speaker_type": "universe",
                    "ref": p["session_id"],
                    "round": round_num,
                    "content": speech_text,
                    "core_memory": updated_mem,
                    "core_memory_edits": edits,
                })

            # 2) 关系人发言（influence 降序；participants 已排序）
            for p in dialog["participants"]:
                if p["type"] != "related":
                    continue
                card = related_cards.get(p["person_ref"])
                if not card:
                    continue
                positions = "\n".join(
                    f"- {kp.get('topic', '')}: {kp.get('stance', '')}（依据: {kp.get('evidence', '')}）"
                    for kp in (card.get("known_positions") or [])
                ) or "-（无明确立场记录）"
                blind = "\n".join(f"- {b}" for b in (card.get("blind_spots") or [])) or "-（无）"

                # 情感四件套
                triggers = card.get("emotional_triggers") or {}
                trigger_lines = [
                    f"- 敞开：{triggers.get('opens_up_when', '') or '—'}",
                    f"- 疏远：{triggers.get('withdraws_when', '') or '—'}",
                    f"- 防御：{triggers.get('defensive_when', '') or '—'}",
                    f"- 表达关心：{triggers.get('shows_care_when', '') or '—'}",
                ]
                conflict = card.get("conflict_pattern") or {}
                conflict_lines = [
                    f"- 冲突方式：{conflict.get('style', '') or '—'}",
                    f"- 冷战：{conflict.get('silence', '') or '—'}",
                    f"- 修复：{conflict.get('repair', '') or '—'}",
                    f"- 接受的道歉：{conflict.get('apology_accepted', '') or '—'}",
                ]
                memory = "\n".join(f"- {m}" for m in (card.get("memory_signature") or [])) or "-（无）"

                # 纠错记录
                correction_records = corrections_map.get(card.get("person_ref", "")) or []
                correction_lines = []
                for cr in correction_records:
                    scene = f"（场景：{cr['scene']}）" if cr.get("scene") else ""
                    wrong = f"不要{cr['wrong']}；" if cr.get("wrong") else ""
                    correction_lines.append(f"- {wrong}{scene}正确做法：{cr['correct']}")
                corrections = "\n".join(correction_lines) or "-（无）"

                current_mem = participant_core_memories.get(p["person_ref"]) or LettaCoreMemoryManager.init_related_core_memory(card, personal_model)
                mem_formatted = LettaCoreMemoryManager.format_core_memory_block(current_mem)

                raw_res = _chat_with_retry(
                    self.llm,
                    messages=[
                        {"role": "system", "content": RELATED_SYSTEM.format(
                            person_ref=card.get("person_ref", ""),
                            relation_label=card.get("relation_kind", "关系人"),
                            core_memory_block=mem_formatted,
                            persona=card.get("persona", ""),
                            core_concern=card.get("core_concern", ""),
                            communication_style=card.get("communication_style", ""),
                            triggers_block="\n".join(trigger_lines),
                            conflict_block="\n".join(conflict_lines),
                            memory_block=memory,
                            corrections_block=corrections,
                            positions_block=positions,
                            blind_spots_block=blind,
                            resistance_clause=card.get("resistance_clause", ""),
                            style_rules=SPEECH_STYLE_RULES,
                        )},
                        {"role": "user", "content": RELATED_USER.format(
                            topic=topic,
                            round_num=round_num,
                            total_rounds=total_rounds,
                            round_focus=_related_round_focus(round_num, total_rounds),
                            universe_summaries_block="\n".join(universe_summaries) or "-（无宇宙推演信息）",
                            prior_block=prior_block(),
                        )},
                    ],
                    max_tokens=800,
                    expect_json=True,
                )
                speech_text, updated_mem, edits = _parse_agent_speech_output(raw_res, current_mem)
                participant_core_memories[p["person_ref"]] = updated_mem

                emit({
                    "speaker": card.get("person_ref", "?"),
                    "speaker_type": "related",
                    "ref": card.get("person_ref"),
                    "round": round_num,
                    "content": speech_text,
                    "core_memory": updated_mem,
                    "core_memory_edits": edits,
                })

        # 3) 主持人审计 (基于全轮次发言实录)
        if progress_callback:
            progress_callback("moderate", None)

        ledger_lines = []
        for p in dialog["participants"]:
            if p["type"] != "universe":
                continue
            session = sessions.get(p["session_id"])
            if not session:
                continue
            facts = "\n".join(
                f"    {e['stage_label']}: {e.get('state_snapshot', '')}"
                for e in (session.get("stage_history") or [])
            )
            ledger_lines.append(
                f"- {self._universe_label(session)}（推演深度 "
                f"{len(session.get('stage_history') or [])}/{len(session.get('stage_plan') or [])}，"
                f"定位: {session.get('source_branch_positioning', '')}）:\n{facts}"
            )

        cards_lines = []
        for p in dialog["participants"]:
            if p["type"] != "related":
                continue
            card = related_cards.get(p["person_ref"])
            if not card:
                continue
            cards_lines.append(
                f"- {card.get('person_ref')}（{card.get('relation_kind', '')}，"
                f"thin={str(bool(card.get('thin'))).lower()}）: "
                f"{card.get('persona', '')}；核心关切: {card.get('core_concern', '')}；"
                f"已知立场: {json.dumps(card.get('known_positions') or [], ensure_ascii=False)}"
            )

        speeches_lines = [
            f"【第 {s.get('round', 1)} 轮 · {s['speaker']}】{'（关系人，单方记述）' if s['speaker_type'] == 'related' else ''}：{s['content']}"
            for s in speeches
        ]

        moderation = _chat_with_retry(
            self.llm,
            messages=[
                {"role": "system", "content": MODERATOR_SYSTEM.format(
                    summary_style=SUMMARY_STYLE_RULES,
                )},
                {"role": "user", "content": MODERATOR_USER.format(
                    topic=topic,
                    ledger_block="\n".join(ledger_lines) or "（无宇宙底账）",
                    cards_block="\n".join(cards_lines) or "（无关系人）",
                    speeches_block="\n\n".join(speeches_lines) or "（无发言）",
                )},
            ],
            max_tokens=8192,
            expect_json=True,
        )

        dialog["moderation"] = moderation
        dialog["transcript"] = speeches
        return dialog

    def interject(
        self,
        dialog: Dict[str, Any],
        speaker_ref: str,
        question: str,
        personal_model: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        用户在圆桌中临时现场追问/质询某个发言者：
        - speaker_ref: session_id (若是宇宙自我) 或 person_ref (若是关系人)
        - question: 用户现场追问内容
        - 返回追加后的 speech 条目
        """
        project_id = dialog["project_id"]
        # 1. 查找目标参与者
        target = None
        for p in dialog.get("participants", []):
            if p.get("session_id") == speaker_ref or p.get("person_ref") == speaker_ref:
                target = p
                break
        if not target:
            # 容错：通过 speaker label 查找
            for p in dialog.get("participants", []):
                if p.get("label") == speaker_ref:
                    target = p
                    break

        # 历史发言上下文
        prior_speeches = dialog.get("transcript", [])
        prior_lines = [
            f"【{s['speaker']}】{'（关系人）' if s.get('speaker_type') == 'related' else ''}：{s['content']}"
            for s in prior_speeches[-8:]
        ]
        prior_block_str = "\n\n".join(prior_lines)

        persona_block = json.dumps({
            "basic_info": personal_model.get("basic_info"),
            "personality": personal_model.get("personality"),
            "current_state": personal_model.get("current_state"),
        }, ensure_ascii=False)
        universe_voice_block = voice_block(personal_model.get("expression_dna") or [])
        if universe_voice_block:
            universe_voice_block += "\n"

        if target and target.get("type") == "universe":
            session = EvolutionStore.get(project_id, target["session_id"])
            if not session:
                raise ValueError("Universe session not found")
            history_lines = []
            for e in session.get("stage_history") or []:
                note = f"（偏离剧本：{e['divergence_note']}）" if e.get("divergence_note") else ""
                history_lines.append(
                    f"- {e['stage_label']}{note}: {e.get('state_snapshot', '')}"
                )

            current_mem = LettaCoreMemoryManager.init_universe_core_memory(session, personal_model)
            mem_formatted = LettaCoreMemoryManager.format_core_memory_block(current_mem)

            system_prompt = UNIVERSE_SYSTEM.format(
                persona_block=persona_block,
                core_memory_block=mem_formatted,
                positioning=session.get("source_branch_positioning", ""),
                stage_label=(session.get("stage_history") or [{}])[-1].get("stage_label", ""),
                depth=len(session.get("stage_history") or []),
                total=len(session.get("stage_plan") or []),
                history_block="\n".join(history_lines) or "-（暂无）",
                voice_block=universe_voice_block,
                style_rules=SPEECH_STYLE_RULES,
            )
            user_prompt = f"""圆桌议题：{dialog['topic']}

圆桌之前的发言记录：
{prior_block_str}

【用户/提问者对你发起现场质询/追问】：
"{question}"

请保持你在本宇宙中的处境、经历与说话风格，直接针对用户的现场质询做出真实回应。不要跳出角色，字数在 120-260 字之间。"""

            raw_res = _chat_with_retry(
                self.llm,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                expect_json=True,
            )
            speech_text, updated_mem, edits = _parse_agent_speech_output(raw_res, current_mem)
            speaker_name = self._universe_label(session)
            speaker_type = "universe"
        else:
            # 关系人
            person_ref = target.get("person_ref") if target else speaker_ref
            cards_data = RelationshipAgentStore.get_current(project_id)
            card = next((c for c in (cards_data.get("cards") if cards_data else []) if c.get("person_ref") == person_ref), None)
            if not card:
                card = {"person_ref": person_ref, "relation_kind": "关系人", "persona": "关系人"}

            current_mem = LettaCoreMemoryManager.init_related_core_memory(card, personal_model)
            mem_formatted = LettaCoreMemoryManager.format_core_memory_block(current_mem)

            corrections_map = RelationshipAgentStore.get_corrections(project_id)
            correction_lines = []
            for cr in corrections_map.get(card.get("person_ref", ""), []):
                scene = f"（场景：{cr['scene']}）" if cr.get("scene") else ""
                wrong = f"不要{cr['wrong']}；" if cr.get("wrong") else ""
                correction_lines.append(f"- {wrong}{scene}正确做法：{cr['correct']}")
            corrections = "\n".join(correction_lines) or "-（无）"

            system_prompt = RELATED_SYSTEM.format(
                person_ref=card.get("person_ref", ""),
                relation_label=card.get("relation_kind", "关系人"),
                core_memory_block=mem_formatted,
                persona=card.get("persona", ""),
                core_concern=card.get("core_concern", ""),
                communication_style=card.get("communication_style", ""),
                triggers_block="-（无）",
                conflict_block="-（无）",
                memory_block="-（无）",
                corrections_block=corrections,
                positions_block="-（无）",
                blind_spots_block="-（无）",
                resistance_clause=card.get("resistance_clause", ""),
                style_rules=SPEECH_STYLE_RULES,
            )
            user_prompt = f"""圆桌议题：{dialog['topic']}

圆桌之前的发言记录：
{prior_block_str}

【用户/当事人对你发起现场质询/追问】：
"{question}"

请保持你的人格卡特征、说话语气与核心关切，直接针对当事人的追问做出真实回应。不要跳出角色，字数在 120-260 字之间。"""

            raw_res = _chat_with_retry(
                self.llm,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                expect_json=True,
            )
            speech_text, updated_mem, edits = _parse_agent_speech_output(raw_res, current_mem)
            speaker_name = card.get("person_ref", "?")
            speaker_type = "related"

        # 记录追问和回应
        interjection_speech = {
            "speaker": "用户现场质询",
            "speaker_type": "user_interjection",
            "ref": "user",
            "target_ref": speaker_ref,
            "target_name": speaker_name,
            "content": question,
            "is_interjection": True
        }
        reply_speech = {
            "speaker": speaker_name,
            "speaker_type": speaker_type,
            "ref": speaker_ref,
            "content": speech_text,
            "core_memory": updated_mem,
            "core_memory_edits": edits,
            "is_interjection_reply": True
        }

        if "transcript" not in dialog:
            dialog["transcript"] = []
        dialog["transcript"].append(interjection_speech)
        dialog["transcript"].append(reply_speech)
        RoundtableStore.save(dialog)
        return reply_speech
