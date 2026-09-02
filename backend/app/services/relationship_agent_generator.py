"""
关系人 Agent 人格卡生成器（C2a）
从 Zep 图谱的 Person 实体 + 个人画像 relationships 出发，
为每位经用户确认的关系人生成一张"人格卡"（persona card）。

认识论定位：单方记述
  关系人 Agent 的全部自我认知来自用户资料中对 TA 的记述，
  因此人格卡内置"反抗条款"——Agent 可以对用户的记述提出异议。

第一版范围限定：图谱 Person 实体中 relation_kind ∈ {family, friend, colleague, acquaintance, mentor, rival, other}
且关联事实 ≥ 1 条；不做 synthetic agent（资料外的虚构人物）。
"""

import json
import re
import time
import concurrent.futures
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, EntityNode

logger = get_logger('prism.relationship.generator')

# 允许生成 Agent 的关系类型
ALLOWED_RELATION_KINDS = {"family", "friend", "colleague", "acquaintance", "mentor", "rival", "other"}
# 自我指称的实体名（排除在候选之外）
SELF_NAMES = {"user", "用户", "本人", "我", "self"}
# 入选所需最少关联事实数
MIN_FACT_COUNT = 1


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


def _chat_json_with_retry(llm: LLMClient, *, messages, max_tokens: int):
    delays = [5, 10, 20, 30]
    for attempt in range(len(delays) + 1):
        try:
            return llm.chat_json(
                messages=messages, temperature=0.4, max_tokens=max_tokens, max_attempts=2
            )
        except Exception as error:
            if attempt >= len(delays) or not _is_transient_api_error(error):
                raise
            logger.warning(f"瞬时 API 错误（第 {attempt + 1} 次），{delays[attempt]} 秒后重试: {error}")
            time.sleep(delays[attempt])
    raise RuntimeError("unreachable")


SYSTEM_PROMPT = """你是一位资深的人物侧写师。你将收到用户资料（日记/简历/感想等）所构建的知识图谱中，关于某位关系人的全部记述，以及用户的个人画像。请为这位关系人生成一张"人格卡"——之后会有一个 Agent 扮演这位关系人参与对话。

最重要的认识论原则——单方记述：
- 你看到的关于此人的全部信息，都来自用户单方面的记述。用户可能误解 TA、美化 TA 或简化 TA
- 因此人格卡中要区分"用户眼中的 TA"与"据此可合理推断的 TA"
- 必须写入反抗空间：如果用户的记述与一个真实、立体的人应有的复杂性冲突（例如把母亲完全描述成控制者），在 resistance_clause 中指出这个 Agent 有权在对话中说"我不认为我会这么说"

铁律：
1. 不虚构：资料中不存在的信息不要编造（尤其禁止虚构亲密细节）；信息不足就如实标注 thin: true
2. blind_spots 是关键产出：用户资料中从未对此人提及的部分（如"从未告诉母亲自己热爱数据分析"），就是这个 Agent 在对话中真实不知道的事
3. known_positions 的每个立场必须给出图谱事实依据
4. communication_style 要具体到说话方式（借谁之口、用什么句式），不要写抽象标签
5. 情感四件套（emotional_triggers / conflict_pattern / memory_signature）遵循"模式提取优先于生平概括"：输出可复现的行为模式，不用抽象形容词；信息不足的子字段留空字符串，不要编造
6. 只输出一个 JSON 对象，不要输出其他文字"""

CARD_PROMPT = """为以下关系人生成精炼紧凑的人格卡，每个字段用一句话简短概括（30字内），严禁冗长，输出 JSON：
{{
  "person_ref": "{person_name}",
  "relation_kind": "{relation_kind}",
  "persona": "一段立体的人物速写（120字以内）：此人是谁、什么背景、什么脾气",
  "core_concern": "TA 最关心用户的什么（不是 TA 自己的什么）",
  "communication_style": "TA 表达关心/反对/焦虑的典型方式（具体到句式和习惯）",
  "emotional_triggers": {{
    "opens_up_when": "什么话题/场合让TA敞开心扉",
    "withdraws_when": "什么时候TA会关闭自己、疏远",
    "defensive_when": "什么时候TA会进入防御、开始反驳",
    "shows_care_when": "TA用什么方式表达关心（行动/言语/沉默的陪伴）"
  }},
  "conflict_pattern": {{
    "style": "TA吵架/反对的方式（讲道理/冷战/爆发/阴阳怪气）",
    "silence": "冷战能持续多久、什么条件下TA先破冰",
    "repair": "吵完后TA怎么和好（主动道歉/假装无事/用行动示好）",
    "apology_accepted": "TA接受什么样的道歉、拒绝什么样的道歉"
  }},
  "memory_signature": ["用户记述中反复出现的场景/象征物/共同习惯（没有则空数组）"],
  "defense_axis": {{
    "pride_anchor": "TA不可触碰的自尊底线或优越感来源（如：'自诩掌柜身份，容不得穷秀才赊账'）",
    "vulnerability": "TA最容易被刺痛或防御的心虚处（如：'怕官府生事，怕街坊议论酒馆掺水'）"
  }},
  "episodic_memories": [
    {{
      "scene": "TA与用户交往中最深刻的具象经历片段",
      "impact": "给TA留下的深刻印象或戒心"
    }}
  ],
  "known_positions": [{{"topic": "", "stance": "", "evidence": "图谱事实依据"}}],
  "documented_quotes": ["用户资料中与此人相关的原文片段（最多3条，没有则空数组）"],
  "blind_spots": ["用户资料中从未对此人提及的关键事实/想法（TA在对话中真实不知道的事）"],
  "resistance_clause": "当用户把TA简化或误解时，TA最可能提出的异议（例如'你总觉得我反对你创业是因为保守，其实我是担心你身体'）",
  "thin": false
}}

关系人事实依据：
{entity_context}

用户个人画像上下文：
{model_context}"""


def _facts_of(entity: EntityNode) -> List[str]:
    return [
        edge.get("fact", "") for edge in (entity.related_edges or [])
        if edge.get("fact")
    ]


def _relation_kind_of(entity: EntityNode) -> Optional[str]:
    attrs = entity.attributes or {}
    kind = str(attrs.get("relation_kind", "") or "").strip().lower()
    if kind in ALLOWED_RELATION_KINDS:
        return kind
    # 属性缺失时从名字/摘要推断（中文常见称谓）
    text = f"{entity.name} {entity.summary or ''}"
    if re.search(r"母亲|妈妈|父亲|爸爸|父母|哥|姐|弟|妹|儿子|女儿|丈夫|妻子|老公|老婆|家", text):
        return "family"
    if re.search(r"同事|领导|上司|老板|导师|主管|掌柜|雇主|东家", text):
        return "colleague"
    if re.search(r"朋友|好友|闺蜜|室友|同学|同乡|熟人", text):
        return "friend"
    if re.search(r"乡绅|举人|债主|官吏|先生|伙计", text):
        return "acquaintance"
    return "other"


class RelationshipAgentGenerator:
    """关系人人格卡生成器"""

    def __init__(self, api_key: Optional[str] = None):
        self.llm = LLMClient(api_key=api_key) if api_key else LLMClient()
        self.reader = ZepEntityReader(api_key=Config.ZEP_API_KEY)

    # ---------- 候选识别（无 LLM 调用） ----------

    def list_candidates(
        self,
        graph_id: str,
        personal_model: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        扫描图谱 Person 实体，识别可生成 Agent 的关系人候选。

        规则：排除 self；relation_kind ∈ {family, friend, colleague}；
        关联事实 ≥ 2 条。与 personal_model.relationships 交叉补充 closeness/influence。
        """
        filtered = self.reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=["Person"],
            enrich_with_edges=True,
        )
        model_rels = {
            (r.get("person") or "").strip(): r
            for r in (personal_model.get("relationships") or [])
            if isinstance(r, dict)
        }

        candidates: List[Dict[str, Any]] = []
        for entity in filtered.entities:
            name = (entity.name or "").strip()
            if not name or name.lower() in SELF_NAMES:
                continue
            attrs = entity.attributes or {}
            if str(attrs.get("relation_kind", "")).strip().lower() == "self":
                continue

            relation_kind = _relation_kind_of(entity)
            if not relation_kind:
                continue

            facts = _facts_of(entity)
            if len(facts) < MIN_FACT_COUNT:
                continue

            rel = model_rels.get(name) or {}
            candidates.append({
                "person_name": name,
                "relation_kind": relation_kind,
                "relation_note": rel.get("relation", "") or entity.summary or "",
                "closeness": rel.get("closeness", ""),
                "influence": rel.get("influence", ""),
                "fact_count": len(facts),
                "facts": facts[:8],
                "thin": len(facts) < 3,
            })

        # 若图谱候选为空或较少，直接从 personal_model.relationships 补充获取
        existing_names = {c["person_name"] for c in candidates}
        for name, rel in model_rels.items():
            if not name or name.lower() in SELF_NAMES or name in existing_names:
                continue
            candidates.append({
                "person_name": name,
                "relation_kind": rel.get("relation") or "other",
                "relation_note": rel.get("influence", "") or rel.get("relation", ""),
                "closeness": rel.get("closeness", ""),
                "influence": rel.get("influence", ""),
                "fact_count": 2,
                "facts": [rel.get("influence", "")] if rel.get("influence") else ["相关人物"],
                "thin": False,
            })

        # 影响力降序（无画像信息时按事实数）
        candidates.sort(key=lambda c: (c.get("influence") != "", c["fact_count"]), reverse=True)
        logger.info(f"识别关系人候选: graph={graph_id}, count={len(candidates)}")
        return candidates

    # ---------- 人格卡生成（每位关系人 1 次 LLM 调用） ----------

    def generate_cards(
        self,
        graph_id: str,
        personal_model: Dict[str, Any],
        selected_names: List[str],
        progress_callback=None,
    ) -> List[Dict[str, Any]]:
        """
        为勾选的关系人生成人格卡（顺序逐个生成，便于进度上报）。

        Args:
            selected_names: 用户勾选的 person_name 列表
        """
        candidates = self.list_candidates(graph_id, personal_model)
        by_name = {c["person_name"]: c for c in candidates}

        unknown = [n for n in selected_names if n not in by_name]
        if unknown:
            raise ValueError(f"以下关系人不在候选列表中: {', '.join(unknown)}")

        model_context = json.dumps({
            key: personal_model.get(key)
            for key in ("basic_info", "current_state", "conflicts", "aspirations")
        }, ensure_ascii=False)

        total = len(selected_names)
        
        def _generate_one_card(index_and_name):
            i, name = index_and_name
            candidate = by_name[name]
            if progress_callback:
                progress_callback("card", f"生成 {name} 的人格卡（{i + 1}/{total}）", i + 1, total)

            entity_context = (
                f"- Person: {name}\n"
                f"  摘要: {candidate.get('relation_note', '') or '-'}\n"
                f"  画像侧关系: closeness={candidate.get('closeness') or '-'}, "
                f"influence={candidate.get('influence') or '-'}\n"
                + "\n".join(f"  fact: {f}" for f in candidate["facts"])
            )

            card = _chat_json_with_retry(
                self.llm,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": CARD_PROMPT.format(
                        person_name=name,
                        relation_kind=candidate["relation_kind"],
                        entity_context=entity_context,
                        model_context=model_context,
                    )},
                ],
                max_tokens=4096,
            )
            card.setdefault("person_ref", name)
            card.setdefault("relation_kind", candidate["relation_kind"])
            card["thin"] = bool(card.get("thin") or candidate.get("thin"))
            card["allow_resistance"] = True  # 反抗条款（用户已确认开启）
            return i, card

        cards_with_idx = []
        max_workers = min(4, len(selected_names))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_generate_one_card, item) for item in enumerate(selected_names)]
            for future in concurrent.futures.as_completed(futures):
                cards_with_idx.append(future.result())

        cards_with_idx.sort(key=lambda x: x[0])
        return [c for _, c in cards_with_idx]
