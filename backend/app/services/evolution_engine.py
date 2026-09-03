"""
人生分支阶段推进引擎（方案 C0）
把方案 A 生成的"剧本式分支"升级为可推演的状态机（EvolutionSession）：
  - 4 维 world_state（career/family/resources/psyche）作为状态锚
  - 单阶段同步推进（每次 advance 一次 LLM 调用）
  - key_assumption 转化为可验证的假设分叉（fork）
  - 用户可注入事件（下一阶段生效）

A 的 timeline 降级为参考轨迹（允许推演偏离，divergence_note 让偏离可见）。
设计见圆桌/推演设计讨论，接口与 docs/PERSONAL_PROFILE_DESIGN.md 惯例一致。
"""

import json
import copy
import time
import uuid
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient, LLMResponseError
from ..utils.logger import get_logger
from ..models.personal_model import PersonalModelStore
from . import realism_layer  # 真实性约束层（存量账本/意外扰动/因果校验）
from .memory_mutator import AtomicMemoryMutator  # Mem0 原子事实状态变更流水线
from .anti_drift_guard import AntiDriftGuard  # Step 4 人格防漂移与保真度审计卫士
from .writing_style import NARRATIVE_STYLE_RULES

logger = get_logger('prism.evolution.engine')

# world_state 的 4 个固定维度（对抗长链推演漂移的状态锚）
WORLD_STATE_DIMS = ("career", "family", "resources", "psyche")


def _is_transient_api_error(error: Exception) -> bool:
    """判断是否为瞬时性 API 错误（与 branch_generator 保持一致）"""
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


def _chat_json_with_retry(
    llm: LLMClient,
    *,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float = 0.5,
):
    """chat_json + 瞬时错误指数退避重试（最多 4 次）"""
    delays = [5, 10, 20, 30]
    for attempt in range(len(delays) + 1):
        try:
            return llm.chat_json(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_attempts=2,
            )
        except Exception as error:
            # 瞬时 API 错误按退避重试；LLM 输出非法 JSON 属内容级错误，
            # 重新生成即可恢复，同样允许有限次重试。
            retryable = _is_transient_api_error(error) or isinstance(error, LLMResponseError)
            if attempt >= len(delays) or not retryable:
                raise
            logger.warning(f"可重试错误（第 {attempt + 1} 次），{delays[attempt]} 秒后重试: {error}")
            time.sleep(delays[attempt])
    raise RuntimeError("unreachable")


SYSTEM_PROMPT = """你是一个人生推演引擎。你在推演一个人的某条人生分支如何随时间演化。
你收到的不是一个剧本，而是一个初始状态、一个分支方向和一系列阶段焦点——结局不由你预设，而是由每个阶段的状态迁移涌现。

铁律：
1. 增量迁移：新阶段的世界状态必须从上一阶段的 4 维状态（career/family/resources/psyche）演化而来，不允许凭空重写或跳变
2. 因果诚实：每个状态变化要有可追溯的原因（本阶段的行动、他人的反应、外部事件）；允许挫折和意外，不粉饰
3. 尊重人格惯性：此人的性格特质（如回避冲突、容易内耗）应持续影响其选择，不会一个阶段就脱胎换骨
4. 尊重边界：不得越过此人明确 want_to_avoid 的东西
5. 推演要具体：写发生了什么事、谁说了什么、结果如何，不写抽象展望
6. 真实性约束（必须严格遵守账面）：输入会附带一张"上阶段末账面"，包括健康分、存款/债务、关系人张力、机会窗口。状态迁移不得直接越过账面（如存款 0 却说经济好转、窗口关闭却说上岸了）
7. 关系人必须发声：每个阶段输入会指定 2 位"必须发声"的关系人，occurred_events 中必须让他们明确说话（有立场），不允许沉默
8. 不可控事件要落地：如果抽到了【好运气/坏运气】事件，必须把它发生的情景、人物对白、连锁后果真实写入 occurred_events，不允许写成"虚惊一场"或"很快解决"
9. 只输出一个 JSON 对象，不要输出其他文字"""


CREATE_PROMPT = """基于以下人生分支与个人画像，为"深度推演"设计阶段计划与假设分叉。

分支方向：{archetype}
分支定位：{positioning}
分支原时间线（参考轨迹）：
{timeline_json}
分支关键假设：{key_assumption}

设计要求：
- stage_plan: {stage_count} 个阶段（按时间正序），每个包含 stage_label（如"未来6个月"/"第1年末"）和 focus（该阶段的核心议题，取自分支时间线但用自己的话重述）
- forks: 0-2 个假设分叉。优先把 key_assumption 转化为一个分叉：在它应该见分晓的阶段（at_stage，1 表示第 1 个阶段）提出问题，给出 2 个选项（假设成立/不成立各自的具体情形）。不要为每阶段都设分叉
- 阶段聚焦要覆盖分支的核心张力，最后一个阶段聚焦"结局收敛"

输出 JSON：
{{
  "stage_plan": [{{"stage_label": "", "focus": ""}}],
  "forks": [{{"at_stage": 1, "question": "", "options": [{{"label": "", "condition": ""}}]}}]
}}

个人画像：

{model_json}"""


ADVANCE_PROMPT = """推演下一个阶段。

分支定位：{positioning}
当前要推演的阶段：{stage_label}
该阶段焦点：{focus}

{state_block}

{memory_block}

{realism_block}

{event_block}

{fork_block}

叙事人称：全程第三人称，主角称呼为「{protagonist}」（可用代词他/她），禁止第二人称「你」——这是观察一个平行宇宙，不是对主角说话。

推演要求（必须精炼，严格控制总字数）：
- world_state: 输出 4 维状态（career/family/resources/psyche），每维 1 句话（25字内）
- occurred_events: 本阶段实际发生的 3 件核心事件，每件 1 句话
- state_snapshot: 80 字以内的阶段概括
- reflections: 1 条心智反思（type + insight 30字内 + grounded_events）
- stakeholder_moves: 1 条关系人博弈行动（person, role, stance, motive, action, demand 均 20字内）
- memory_mutations（Mem0 原子状态变更，1-2 条）：
  * action: "ADD" | "UPDATE" | "DELETE" | "NOOP"
  * target_id: 被修改/作废的事实 ID（如 "mem_0_init_1"，ADD/NOOP 为 null）
  * subject: 涉及主体
  * category: "identity" | "resource" | "relation" | "belief" | "milestone"
  * fact: 极简事实（20字内）
  * reason: 原因简述（10字内）
- divergence_note: 若本阶段走向明显偏离了分支原时间线（{timeline_json}），用一句话说明偏离点；无明显偏离则输出 null
- realism_delta（新增）：根据本阶段实际发生的事，估算对真实性账面的增量变化。仅输出 JSON 对象，key 范围：
  * health_delta: 整数，本阶段健康分的净变化
  * cash_delta: 整数，存款月数当量的变化（赚钱/投资/继承 为正，裸辞/治病/败家 为负）
  * debt_delta: 整数，债务当量的变化
  * stress_delta: 整数，压力残留的变化
  * tension_deltas: 对象，key=关系人名，value=张力变化（未出现的关系人可以不列）
  * window_takens: 字符串数组，本阶段取得的窗口名；错过的什么都不要写
  没有变化的 key 可以省略。

{style_rules}

输出 JSON：
{{
  "world_state": {{"career": "", "family": "", "resources": "", "psyche": ""}},
  "occurred_events": [""],
  "state_snapshot": "",
  "reflections": [
    {{
      "type": "self_paradox|relation_insight|price_consensus",
      "insight": "本阶段形成的深刻认知",
      "grounded_events": ["依据事件片段"]
    }}
  ],
  "stakeholder_moves": [
    {{
      "person": "关系人名",
      "role": "身份",
      "stance": "confrontational|transactional|supportive",
      "motive": "动机",
      "action": "具体主动施压或行动",
      "demand": "明确要求或通牒"
    }}
  ],
  "memory_mutations": [
    {{
      "action": "ADD|UPDATE|DELETE|NOOP",
      "target_id": null,
      "subject": "",
      "category": "identity|resource|relation|belief|milestone",
      "fact": "单句事实（25字内）",
      "reason": "原因（15字内）"
    }}
  ],
  "divergence_note": null,
  "realism_delta": {{}}
}}"""


class EvolutionEngine:
    """分支阶段推进引擎：一个会话一个状态机"""

    def __init__(self, api_key: Optional[str] = None):
        # 延迟创建 LLM 客户端：纯本地操作（例如裁决真实性断路器分叉）
        # 不应因为测试/离线环境没有 API Key 而无法执行。
        self._api_key = api_key
        self._llm: Optional[LLMClient] = None

    @property
    def llm(self) -> LLMClient:
        """首次真正需要生成内容时才校验并创建 LLM 客户端。"""
        if self._llm is None:
            self._llm = LLMClient(api_key=self._api_key)
        return self._llm

    @llm.setter
    def llm(self, value: LLMClient) -> None:
        # 保留测试和集成方注入 fake client 的能力。
        self._llm = value

    # ---------- 画像裁剪（推演所需的稳定人格锚） ----------

    @staticmethod
    def _model_anchor(personal_model: Dict[str, Any]) -> Dict[str, Any]:
        anchor = {
            key: personal_model.get(key)
            for key in (
                "basic_info", "personality", "aspirations",
                "current_state", "conflicts", "emotional_patterns",
            )
        }
        return anchor

    # ---------- 创建会话 ----------

    def create_session(
        self,
        project_id: str,
        branch: Dict[str, Any],
        personal_model: Dict[str, Any],
        stage_count: int = 4,
        relationship_cards: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        从 A 分支创建推演会话（1 次 LLM 调用生成 stage_plan + forks）。

        Args:
            branch: BranchStore 产出的一条完整分支对象
            personal_model: 当前个人模型
            stage_count: 推演深度（3-6）
        """
        stage_count = max(3, min(6, int(stage_count)))
        archetype = branch.get("archetype", "")
        timeline = branch.get("timeline") or []

        result = _chat_json_with_retry(
            self.llm,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": CREATE_PROMPT.format(
                    archetype=archetype,
                    positioning=branch.get("positioning", ""),
                    timeline_json=json.dumps(timeline, ensure_ascii=False),
                    key_assumption=branch.get("key_assumption", ""),
                    stage_count=stage_count,
                    model_json=json.dumps(self._model_anchor(personal_model), ensure_ascii=False),
                )},
            ],
            max_tokens=4096,
        )

        stage_plan = result.get("stage_plan") or []
        if not stage_plan:
            raise ValueError("阶段计划生成失败：LLM 未返回有效 stage_plan")
        stage_plan = stage_plan[:stage_count]

        forks = []
        for i, fork in enumerate(result.get("forks") or []):
            options = fork.get("options") or []
            if len(options) < 2:
                continue
            at_stage = fork.get("at_stage", 1)
            try:
                at_stage = max(1, min(len(stage_plan), int(at_stage)))
            except (TypeError, ValueError):
                at_stage = 1
            forks.append({
                "fork_id": f"fork_{i + 1}",
                "at_stage": at_stage,
                "question": fork.get("question", ""),
                "options": options[:2],
                "resolved": None,
            })

        session = {
            "session_id": f"evo_{uuid.uuid4().hex[:12]}",
            "project_id": project_id,
            "source_branch_archetype": archetype,
            "source_branch_positioning": branch.get("positioning", ""),
            "source_branch_timeline": timeline,
            "source_branch_assumption": branch.get("key_assumption", ""),
            "source_model_version": personal_model.get("model_version"),
            # 叙事主角称呼（画像昵称），推演全程第三人称使用
            "protagonist": (personal_model.get("basic_info") or {}).get("nickname") or "主角",
            "stage_plan": stage_plan,
            "stage_history": [],
            "pending_forks": forks,
            "user_events": [],
            "status": "active",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            # Mem0 活跃原子记忆库
            "active_memories": AtomicMemoryMutator.init_session_memories(personal_model, branch),
            # Realism Layer 账本：会在 advance 之间持久化、在 prepare_stage_realism 中读取修改
            "realism_state": realism_layer.init_realism_state(
                personal_model,
                relationship_cards or [],
                stage_plan,
            ),
        }
        logger.info(
            f"创建推演会话: project={project_id}, archetype={archetype}, "
            f"stages={len(stage_plan)}, forks={len(forks)}, "
            f"health={session['realism_state']['health_score']}, "
            f"rels={len(session['realism_state']['relationships'])}"
        )
        return session

    # ---------- 推进一个阶段 ----------

    def advance(
        self,
        session: Dict[str, Any],
        injected_event: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        推进一个阶段（1 次 LLM 调用，同步返回）。

        Returns:
            更新后的 session（追加 stage_history 条目）；
            若下一阶段被未决分叉挡住，返回 {"fork_required": True, "fork": {...}, "session": ...}
        """
        if session.get("status") != "active":
            raise ValueError(f"会话状态为 {session.get('status')}，无法推进")

        original_session = session
        session = copy.deepcopy(session)

        def commit_session() -> Dict[str, Any]:
            original_session.clear()
            original_session.update(session)
            return original_session
        stage_runs = session.setdefault("stage_runs", {})
        if request_id:
            for run in stage_runs.values():
                if isinstance(run, dict) and run.get("request_id") == request_id:
                    return {"fork_required": bool(run.get("fork_required")), "fork": run.get("fork"), "session": commit_session(), "replayed": True}

        history: List[Dict[str, Any]] = session["stage_history"]
        plan: List[Dict[str, Any]] = session["stage_plan"]
        next_index = len(history)  # 0-based
        if next_index >= len(plan):
            raise ValueError("全部阶段已推演完成")

        # 记录用户注入事件（下一阶段 = 本阶段生效）
        if injected_event:
            session["user_events"].append({
                "at_stage": next_index + 1,  # 1-based 阶段号
                "event": injected_event,
                "injected": True,
            })

        # 1. 检查是否有挡在该阶段入口的未决分叉
        stage_no = next_index + 1
        blocking_fork = next(
            (f for f in session["pending_forks"]
             if f["at_stage"] == stage_no and f.get("resolved") is None),
            None,
        )
        if blocking_fork:
            if request_id:
                stage_runs[str(stage_no)] = {"request_id": request_id, "status": "fork_required", "fork_required": True, "fork": blocking_fork}
            return {"fork_required": True, "fork": blocking_fork, "session": commit_session()}

        # 2. 确定性真实感断路器拦截（0 Token 本地状态机断言）
        realism_state: Dict[str, Any] = session.setdefault("realism_state", {})
        circuit_fork = realism_layer.check_circuit_breakers(
            realism_state=realism_state,
            stage_no=stage_no,
            existing_forks=session.get("pending_forks", []),
        )
        if circuit_fork:
            session.setdefault("pending_forks", []).append(circuit_fork)
            if request_id:
                stage_runs[str(stage_no)] = {"request_id": request_id, "status": "fork_required", "fork_required": True, "fork": circuit_fork}
            logger.warning(
                f"会话 {session.get('session_id')} 阶段 {stage_no} 触发真实感断路器拦截: "
                f"{circuit_fork.get('circuit_breaker')}"
            )
            return {"fork_required": True, "fork": circuit_fork, "session": commit_session()}

        stage = plan[next_index]

        # 状态块：第一阶段用画像 current_state 作初始状态
        prev_world_state: Dict[str, Any] = {}
        if history:
            prev = history[-1]
            prev_world_state = prev.get("world_state", {}) or {}
            state_block = (
                f"上一阶段（{history[-1].get('stage_label', '')}）结束时的世界状态：\n"
                f"{json.dumps(prev_world_state, ensure_ascii=False, indent=2)}\n"
                f"上一阶段叙事：{prev.get('state_snapshot', '')}"
            )
        else:
            state_block = (
                "这是第一个阶段。此人的当前状态（推演起点）：\n"
                f"{session.get('initial_state', '')}"
            )

        # Realism 块：上阶段末账面 + 随机意外事件（副作用：事件效应已写到 realism_state）
        realism_state: Dict[str, Any] = session.setdefault("realism_state", {})
        prev_realism_snapshot = json.loads(json.dumps(realism_state))  # 校验用快照
        realism_block, life_event = realism_layer.prepare_stage_realism(
            realism_state,
            session_id=session.get("session_id", "evo_anon"),
            stage_no=stage_no,
        )

        # 事件块：本阶段应生效的用户事件
        due_events = [
            e["event"] for e in session["user_events"]
            if e.get("at_stage") == stage_no
        ]
        event_block = (
            f"本阶段用户注入的事件（必须发生并产生真实后果）：\n- " + "\n- ".join(due_events)
            if due_events else "本阶段无用户注入事件。"
        )

        # 分叉块：已裁决的分叉条件
        fork_notes = []
        for fork in session["pending_forks"]:
            if fork.get("resolved") is None:
                continue
            if stage_no == fork["at_stage"] or (
                history and fork["at_stage"] == len(history)
            ):
                choice = fork["resolved"]
                fork_notes.append(
                    f"分叉「{fork['question']}」已裁决为「{choice.get('label', '')}」：{choice.get('condition', '')}（本阶段起按此因果线推演）"
                )
        fork_block = (
            "\n".join(fork_notes) if fork_notes else "无分叉条件。"
        )

        def _build_messages(extra_reminder: str = "") -> List[Dict[str, str]]:
            extra = f"\n【修正提示】{extra_reminder}\n" if extra_reminder else ""
            return [
                {"role": "system", "content": SYSTEM_PROMPT + extra},
                {"role": "user", "content": ADVANCE_PROMPT.format(
                    positioning=session.get("source_branch_positioning", ""),
                    stage_label=stage.get("stage_label", ""),
                    focus=stage.get("focus", ""),
                    state_block=state_block,
                    memory_block=AtomicMemoryMutator.format_active_memories_block(session.get("active_memories") or []),
                    realism_block=realism_block,
                    event_block=event_block,
                    fork_block=fork_block,
                    timeline_json=json.dumps(session.get("source_branch_timeline") or [], ensure_ascii=False),
                    protagonist=session.get("protagonist") or "主角",
                    style_rules=NARRATIVE_STYLE_RULES,
                )},
            ]

        # 调用 LLM，最多带一次因果校验重试
        causal_violations: List[str] = []
        result: Dict[str, Any] = {}
        for attempt in range(2):
            extra = (
                "上一次返回的 world_state 违反了以下因果铁律，请逐项修正后重新输出：\n- "
                + "\n- ".join(causal_violations)
                if causal_violations else ""
            )
            result = _chat_json_with_retry(
                self.llm,
                messages=_build_messages(extra),
                max_tokens=8192,
            )
            world_state_candidate = result.get("world_state") or {}
            # 因果校验
            causal_violations = realism_layer.check_causal_violations(
                prev_realism=prev_realism_snapshot,
                prev_world_state=prev_world_state,
                new_world_state={dim: str(world_state_candidate.get(dim, "") or "")
                                 for dim in WORLD_STATE_DIMS},
            )
            if not causal_violations:
                break
            logger.warning(
                f"会话 {session['session_id']} 阶段 {stage_no} 因果校验未通过（attempt {attempt+1}）："
                f"{causal_violations}"
            )

        world_state = result.get("world_state") or {}
        world_state = {dim: str(world_state.get(dim, "") or "") for dim in WORLD_STATE_DIMS}

        # ---- 落账：把 LLM 返回的 realism_delta + 窗口取得 合并到 realism_state ----
        delta: Dict[str, Any] = result.get("realism_delta") or {}
        if isinstance(delta, dict):
            # health
            if isinstance(delta.get("health_delta"), int):
                realism_state["health_score"] = max(
                    0, min(100, realism_state.get("health_score", 80) + delta["health_delta"])
                )
            # finance
            fl = realism_state.setdefault("finance_ledger", {"cash_months": 2, "debt_months": 0, "income_stability": 2})
            if isinstance(delta.get("cash_delta"), int):
                fl["cash_months"] = max(0, fl.get("cash_months", 2) + delta["cash_delta"])
            if isinstance(delta.get("debt_delta"), int):
                fl["debt_months"] = max(0, fl.get("debt_months", 0) + delta["debt_delta"])
            # stress
            if isinstance(delta.get("stress_delta"), int):
                realism_state["stress_carryover"] = max(
                    0, min(100, realism_state.get("stress_carryover", 20) + delta["stress_delta"])
                )
            # tension（按名字匹配）
            tension_deltas = delta.get("tension_deltas")
            if isinstance(tension_deltas, dict):
                for rel in realism_state.get("relationships", []):
                    if rel.get("name") in tension_deltas and isinstance(tension_deltas[rel["name"]], int):
                        rel["tension"] = max(0, min(100, rel["tension"] + tension_deltas[rel["name"]]))
                        rel["last_event"] = "（本阶段互动）"
            # window takens（按名字前缀匹配）
            window_takens = delta.get("window_takens") or []
            if isinstance(window_takens, list):
                for w in realism_state.get("windows", []) or []:
                    wname = w.get("name") or ""
                    if any(t[:4] and t[:4] in wname for t in window_takens if isinstance(t, str)):
                        w["taken"] = True
                for w in realism_state.get("spontaneous_windows", []) or []:
                    wname = w.get("name") or ""
                    if any(t[:4] and t[:4] in wname for t in window_takens if isinstance(t, str)):
                        w["taken"] = True

        # realism_state 快照给前端（stage 级别的健康/财务/压力/关系张力）
        stage_realism_snapshot = {
            "health_score": realism_state.get("health_score"),
            "finance": {
                "cash_months": realism_state["finance_ledger"].get("cash_months"),
                "debt_months": realism_state["finance_ledger"].get("debt_months"),
                "income_stability": realism_state["finance_ledger"].get("income_stability"),
                "known": realism_state["finance_ledger"].get("known", True),
                "source": realism_state["finance_ledger"].get("source", "observed"),
            },
            "stress_carryover": realism_state.get("stress_carryover"),
            "relationships": [
                {"name": r.get("name"), "role": r.get("role"), "tension": r.get("tension"),
                 "last_event": r.get("last_event")}
                for r in realism_state.get("relationships", [])
            ],
            "life_event": {
                "id": life_event.get("id"),
                "kind": life_event.get("kind"),
                "template": life_event.get("template"),
            } if life_event else None,
            "causal_violations_remaining": causal_violations or None,
        }

        reflections_data = [
            {
                "type": str(r.get("type", "self_paradox")),
                "insight": str(r.get("insight", "")),
                "grounded_events": [str(ge) for ge in (r.get("grounded_events") or []) if ge],
            }
            for r in (result.get("reflections") or [])
            if isinstance(r, dict) and r.get("insight")
        ]

        stakeholder_moves_data = [
            {
                "person": str(m.get("person", "")),
                "role": str(m.get("role", "")),
                "stance": str(m.get("stance", "transactional")),
                "motive": str(m.get("motive", "")),
                "action": str(m.get("action", "")),
                "demand": str(m.get("demand", "")),
            }
            for m in (result.get("stakeholder_moves") or [])
            if isinstance(m, dict) and m.get("person") and (m.get("action") or m.get("demand"))
        ]

        # ---- Mem0: 原子记忆变更应用 ----
        current_memories = session.get("active_memories")
        if current_memories is None:
            # 兼容老会话
            current_memories = []
        updated_memories, validated_mutations = AtomicMemoryMutator.apply_mutations(
            active_memories=current_memories,
            raw_mutations=result.get("memory_mutations") or [],
            stage_index=next_index + 1,
        )
        session["active_memories"] = updated_memories

        entry = {
            "stage_index": next_index + 1,
            "stage_label": stage.get("stage_label", f"阶段{next_index + 1}"),
            "focus": stage.get("focus", ""),
            "world_state": world_state,
            "reflections": reflections_data,
            "stakeholder_moves": stakeholder_moves_data,
            "memory_mutations": validated_mutations,
            "active_memories_count": len(updated_memories),
            "occurred_events": [str(e) for e in (result.get("occurred_events") or []) if e],
            "state_snapshot": result.get("state_snapshot", ""),
            "divergence_note": result.get("divergence_note"),
            "realism": stage_realism_snapshot,  # 真实性快照：给前端可视化
        }
        # 人格防漂移审计与保真度评估 (Step 4)
        proj_id = session.get("project_id", "")
        pm = PersonalModelStore.get_current(proj_id) if proj_id else {}
        entry["anti_drift"] = AntiDriftGuard.evaluate_stage_fidelity(
            stage_entry=entry,
            personal_model=pm or {},
            active_memories=updated_memories,
        )
        history.append(entry)

        if len(history) >= len(plan):
            session["status"] = "completed"

        if request_id:
            stage_runs[str(stage_no)] = {"request_id": request_id, "status": "committed", "fork_required": False}

        logger.info(
            f"推进会话 {session['session_id']} → 阶段 {next_index + 1}/{len(plan)}"
            f"  health→{realism_state.get('health_score')}"
            f"  cash→{realism_state['finance_ledger'].get('cash_months')}"
            f"  stress→{realism_state.get('stress_carryover')}"
            f"  life_event→{(life_event or {}).get('id', 'none')}"
            + (f"  violations→{causal_violations}" if causal_violations else "")
        )
        return {"fork_required": False, "session": commit_session()}

    # ---------- 解决假设分叉 ----------

    def resolve_fork(
        self,
        session: Dict[str, Any],
        fork_id: str,
        option_index: int,
    ) -> Dict[str, Any]:
        """裁决分叉：记录选择，下一阶段起按所选因果线推演（无 LLM 调用）"""
        fork = next(
            (f for f in session["pending_forks"] if f["fork_id"] == fork_id), None
        )
        if not fork:
            raise ValueError(f"分叉不存在: {fork_id}")
        if fork.get("resolved") is not None:
            resolved_index = (fork.get("resolved") or {}).get("option_index")
            if resolved_index == int(option_index):
                return session
            raise ValueError("该分叉已裁决")
        options = fork.get("options") or []
        if not (0 <= int(option_index) < len(options)):
            raise ValueError("无效的选项序号")
        effects = options[option_index].get("effects") or {}
        if fork.get("is_emergency") and not effects:
            raise ValueError("紧急断路器选项必须包含结构化 effects")

        fork["resolved"] = {
            "option_index": int(option_index),
            "label": options[option_index].get("label", ""),
            "condition": options[option_index].get("condition", ""),
            "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        state = session.setdefault("realism_state", {})
        finance = state.setdefault("finance_ledger", {"cash_months": 2, "debt_months": 0, "income_stability": 2})
        before = {
            "health_score": state.get("health_score", 80),
            "cash_months": finance.get("cash_months", 2),
            "debt_months": finance.get("debt_months", 0),
            "stress_carryover": state.get("stress_carryover", 20),
        }
        for key, attr in (("health_delta", "health_score"), ("stress_delta", "stress_carryover")):
            if isinstance(effects.get(key), int):
                limit = (0, 100)
                state[attr] = max(limit[0], min(limit[1], state.get(attr, before[attr]) + effects[key]))
        finance_effects = effects.get("finance") or {}
        for key, attr in (("cash_months_delta", "cash_months"), ("debt_months_delta", "debt_months")):
            if isinstance(finance_effects.get(key), int):
                finance[attr] = max(0, finance.get(attr, before[attr]) + finance_effects[key])
        relation_effect = effects.get("relationship") or {}
        if isinstance(relation_effect, dict):
            for rel in state.get("relationships", []):
                if rel.get("name") == relation_effect.get("person"):
                    if isinstance(relation_effect.get("tension_delta"), int):
                        rel["tension"] = max(0, min(100, rel.get("tension", 0) + relation_effect["tension_delta"]))
                    if relation_effect.get("status"):
                        rel["status"] = relation_effect["status"]
        after = {
            "health_score": state.get("health_score"),
            "cash_months": finance.get("cash_months"),
            "debt_months": finance.get("debt_months"),
            "stress_carryover": state.get("stress_carryover"),
        }
        fork["resolved"]["effects"] = effects
        fork["resolved"]["ledger_before"] = before
        fork["resolved"]["ledger_after"] = after
        breaker_key = fork.get("breaker_key") or fork.get("circuit_breaker")
        if breaker_key:
            episodes = state.setdefault("breaker_episodes", {})
            episode = episodes.setdefault(breaker_key, {"episode_id": fork.get("episode_id")})
            episode["status"] = "acknowledged"
            episode["resolved_stage"] = fork.get("at_stage")
        logger.info(f"会话 {session['session_id']} 裁决分叉 {fork_id}: {fork['resolved']['label']}")
        return session

    # ---------- 辅助 ----------

    @staticmethod
    def prepare_initial_state(session: Dict[str, Any], personal_model: Dict[str, Any]) -> None:
        """把画像 current_state 预写入会话（第一阶段推演的起点）"""
        session["initial_state"] = personal_model.get("current_state", "")
        # basic_info 补充上下文（P1-4：过滤空值，只保留有信息量的字段，人类可读格式）
        basic = personal_model.get("basic_info") or {}
        label_map = {
            "age_range": "年龄段",
            "age": "年龄",
            "gender": "性别",
            "location": "所在城市",
            "industry": "行业",
            "current_status": "当前状态",
            "education_level": "学历",
            "financial_state": "财务状况",
        }
        parts = [
            f"{label_map.get(key, key)}: {value}"
            for key, value in basic.items()
            if value not in (None, "", []) and str(value).strip()
        ]
        if parts:
            session["initial_state"] += "\n（基本信息: " + "；".join(parts) + "）"
