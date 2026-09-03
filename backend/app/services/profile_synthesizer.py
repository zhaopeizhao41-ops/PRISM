"""
个人画像合成器
从 Zep 个人图谱读取实体与事实，经三阶段 LLM 合成为稳定的个人模型。

阶段1 快照分区: basic_info / personality / values / skills / interests / emotional_patterns /
             expression_dna（表达基因）/ decision_patterns（决策模式）
阶段2 叙事分区: timeline / milestones / relationships / aspirations
阶段3 综合判断: current_state / conflicts / source_coverage / open_questions

设计文档见 docs/PERSONAL_PROFILE_DESIGN.md 第五节。
"""

import json
import time
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, EntityNode
from .profile_materials import MATERIAL_CONFIDENCE

logger = get_logger('prism.profile.synthesizer')

# 实体类型 → 快照分区
SNAPSHOT_TYPE_MAP = {
    "Trait": "personality",
    "Value": "values",
    "Skill": "skills",
    "Interest": "interests",
    "EmotionalPattern": "emotional_patterns",
}

# 实体类型 → 叙事分区
NARRATIVE_TYPE_MAP = {
    "Experience": "timeline",
    "Milestone": "milestones",
    "Person": "relationships",
    "Aspiration": "aspirations",
}

SOURCE_VALUES = set(MATERIAL_CONFIDENCE.keys()) | {"inference"}


def _is_transient_api_error(error: Exception) -> bool:
    """判断是否为瞬时性 API 错误（限流/高负载），值得退避重试"""
    message = str(error).lower()
    # 日配额耗尽：重试无意义，直接失败
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
    progress_callback=None,
    stage: str = "",
) -> Dict[str, Any]:
    """chat_json + 瞬时错误指数退避重试（最多 4 次，总等待约 45 秒）"""
    delays = [5, 10, 20, 30]
    for attempt in range(len(delays) + 1):
        try:
            return llm.chat_json(
                messages=messages, temperature=0.3, max_tokens=max_tokens, max_attempts=2
            )
        except Exception as error:
            if attempt >= len(delays) or not _is_transient_api_error(error):
                raise
            delay = delays[attempt]
            logger.warning(
                f"瞬时 API 错误（第 {attempt + 1} 次），{delay} 秒后重试: {error}"
            )
            if progress_callback:
                progress_callback(stage, f"LLM 服务繁忙，{delay} 秒后自动重试…")
            time.sleep(delay)
    raise RuntimeError("unreachable")


def _entities_to_context(entities: List[EntityNode]) -> str:
    """实体列表 → LLM 输入文本（含属性与相关事实）"""
    lines: List[str] = []
    for e in entities:
        entity_type = e.get_entity_type() or "?"
        attrs = e.attributes or {}
        attr_str = "; ".join(f"{k}={v}" for k, v in attrs.items() if v) or "-"
        line = f"- [{entity_type}] {e.name} (attrs: {attr_str})"
        facts = [edge.get("fact", "") for edge in e.related_edges if edge.get("fact")]
        if facts:
            for fact in facts[:5]:
                line += f"\n    fact: {fact}"
        lines.append(line)
    return "\n".join(lines) if lines else "（图谱中该分区无实体）"


def _manifest_source_summary(manifest: List[Dict[str, Any]]) -> Dict[str, float]:
    """资料清单 → source_coverage（按字符占比）"""
    total = sum(m.get("char_count", 0) for m in manifest) or 1
    coverage: Dict[str, float] = {}
    for m in manifest:
        mtype = m.get("material_type", "other")
        coverage[mtype] = coverage.get(mtype, 0) + m.get("char_count", 0) / total
    return {k: round(v, 2) for k, v in coverage.items()}


def _raw_text_excerpt(raw_text: Optional[str], limit: int = 4000) -> str:
    """原文节选：表达基因等语言风格证据无法从图谱实体获得，需看原文。

    过长时取头 + 尾（开头通常含称谓/开场白，结尾常有余味），保留 header 行。
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    if len(text) <= limit:
        return text
    head = limit * 5 // 8
    tail = limit - head
    return text[:head] + "\n……（中段省略）……\n" + text[-tail:]


def _stage1_context(
    entities_context: str,
    raw_text: Optional[str],
) -> str:
    """Stage1 上下文 = 图谱实体事实 + 原文节选（语言风格证据）"""
    excerpt = _raw_text_excerpt(raw_text)
    if not excerpt:
        return entities_context
    return (
        entities_context
        + "\n\n原文节选（来自用户提交的材料原文，仅用于 expression_dna 等需要语言风格证据的"
        "分区提取，example 尽量引用原文；其中的事实性内容已在上面的图谱实体里，不要重复提取）：\n"
        + excerpt
    )


def _evidence_context(manifest: List[Dict[str, Any]], limit: int = 9000) -> str:
    """Expose a bounded, addressable local evidence index to the model."""
    lines: List[str] = []
    used = 0
    for material in manifest or []:
        material_id = material.get("material_id") or "?"
        for chunk in material.get("chunks") or []:
            text = " ".join(str(chunk.get("text") or "").split())
            if not text:
                continue
            line = f"- material_id={material_id} chunk_id={chunk.get('chunk_id')} text={text}"
            if used + len(line) > limit:
                return "\n".join(lines) or "（证据索引为空）"
            lines.append(line)
            used += len(line)
    return "\n".join(lines) or "（证据索引为空）"


def _quote_span(chunk_text: str, quote: Any) -> Optional[Dict[str, int]]:
    """Find a conservative span for a model-provided quote."""
    quote_text = str(quote or "").strip()
    if len(quote_text) < 4:
        return None
    direct = chunk_text.find(quote_text)
    if direct >= 0:
        return {"start": direct, "end": direct + len(quote_text)}
    # Compare whitespace-normalized text while retaining original offsets.
    normalized = " ".join(chunk_text.split())
    normalized_quote = " ".join(quote_text.split())
    start = normalized.find(normalized_quote)
    if start < 0:
        return None
    # Rebuild an offset map from normalized characters to the original string.
    offsets: List[int] = []
    previous_space = False
    for index, char in enumerate(chunk_text):
        if char.isspace():
            if not previous_space:
                offsets.append(index)
            previous_space = True
        else:
            offsets.append(index)
            previous_space = False
    if start >= len(offsets) or start + len(normalized_quote) - 1 >= len(offsets):
        return None
    end_index = offsets[start + len(normalized_quote) - 1] + 1
    return {"start": offsets[start], "end": end_index}


def _backfill_evidence_refs(data: Dict[str, Any], manifest: List[Dict[str, Any]]) -> List[str]:
    """Fill refs only when a quote can be verified against the local index."""
    warnings: List[str] = []
    by_type = {}
    for material in manifest or []:
        by_type.setdefault(material.get("material_type", "other"), []).append(material)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            source = value.get("source")
            if source and source != "inference" and isinstance(source, str):
                refs = value.get("evidence_refs")
                if not isinstance(refs, list) or not refs:
                    # Evidence-bearing fields are deliberately limited to avoid
                    # treating an LLM paraphrase as a source citation.
                    quotes = [value.get(key) for key in ("quote", "evidence", "example")]
                    candidates = by_type.get(source, [])
                    for quote in quotes:
                        if not isinstance(quote, str):
                            continue
                        found = []
                        for material in candidates:
                            for chunk in material.get("chunks") or []:
                                span = _quote_span(str(chunk.get("text") or ""), quote)
                                if span:
                                    found.append((material, chunk, span, quote))
                        if len(found) == 1:
                            material, chunk, span, matched_quote = found[0]
                            value["evidence_refs"] = [{
                                "material_id": material.get("material_id"),
                                "chunk_id": chunk.get("chunk_id"),
                                "span": span,
                                "quote": matched_quote,
                            }]
                            break
                    if not value.get("evidence_refs"):
                        value["source"] = "inference"
                        value["traceability"] = "unverified"
                        warnings.append("missing_evidence_refs")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return sorted(set(warnings))


SYSTEM_PROMPT_TEMPLATE = """你是一位资深的用户研究员与心理测量分析师。你将收到一个人的人生资料所构建的知识图谱中提取的实体与事实。请把它们合成为结构化的个人画像分区。

本项目实际存在的材料类型只有：{available_sources}。
source 只能从上述类型与 "inference" 中选择——标注一个本项目并不存在的材料类型（如表单/简历）是严重错误，宁可选 inference。

铁律：
1. 每个结论必须标注 source，取值只能是: {allowed_sources}
   source 不是证据凭据：只要不是 inference，必须同时返回 evidence_refs（material_id/chunk_id/span/quote）。
2. 图谱中没有的信息不要编造；可基于多处证据做温和推断，但必须标 source: "inference"
3. 用户的自我评价与行为证据是两个维度：自评写入 self_view（如适用），行为证据写入 observed（如适用），不要互相覆盖
4. 出现矛盾时：按可信度权重裁决主结论（structured_form > resume > chat_log > diary > reflection > preference），但把矛盾原样记入 conflicts 数组
5. 情绪化表述（如"我一事无成"）不作为事实采纳，转换为 emotional_patterns 线索
6. 语言人称：画像是观察档案，不是判词——结论的主语尽量落在证据上而非人身上（写"日记中三次出现回避冲突的情境"，不写"你回避冲突"）；禁止"你是…的人"式人格判词；推断性结论（source 为 inference）用"可能/似乎"等限定语；自评与行为证据在措辞上保持区分（自述…/行为记录显示…）
7. 只输出一个 JSON 对象，不要输出其他文字"""


def _build_system_prompt(manifest: List[Dict[str, Any]]) -> str:
    """资料清单 → 实际存在的材料类型集合 → 注入系统提示词"""
    present = {
        m.get("material_type", "other")
        for m in manifest
        if m.get("material_type")
    }
    return SYSTEM_PROMPT_TEMPLATE.format(
        available_sources=" / ".join(sorted(present)) if present else "（未知，禁止猜测来源类型，一律标 inference）",
        allowed_sources=" / ".join(sorted(present | {"inference"})) if present else "inference",
    )

STAGE1_PROMPT = """请合成以下快照分区，输出 JSON：
{{
  "basic_info": {{"age_range": "", "gender": null, "location": "", "industry": "", "current_status": "", "education_level": null, "financial_state": null}},
  "personality": {{
    "mbti": {{"value": "", "confidence": "high|medium|low", "conflict_note": null}},
    "big5": {{"openness": null, "conscientiousness": null, "extraversion": null, "agreeableness": null, "neuroticism": null}},
    "self_view": [{{"trait": "", "source": ""}}],
    "observed": [{{"trait": "", "source": "", "evidence": ""}}]
  }},
  "values": [{{"domain": "", "stance": "", "source": ""}}],
  "skills": [{{"name": "", "domain": "", "proficiency": "", "source": ""}}],
  "interests": [{{"category": "", "item": "", "intensity": "", "source": ""}}],
  "emotional_patterns": [{{"pattern_kind": "", "trigger": "", "source": "", "evidence": ""}}],
  "expression_dna": [{{"feature": "", "scene": "", "example": "", "source": ""}}],
  "decision_patterns": [{{"pattern": "", "style": "", "evidence": "", "source": ""}}],
  "defense_mechanisms": {{
    "pride_anchors": [{{"anchor": "尊严与骄傲底线", "evidence": "事实依据", "defense_behavior": "受挑战时的应激言行", "source": ""}}],
    "trauma_triggers": [{{"trigger": "敏感创伤/羞耻话题", "evidence": "事实依据", "response_pattern": "应激反应模式", "source": ""}}]
  }},
  "conflicts": [{{"field": "", "views": [""], "resolution": ""}}]
}}
分区说明：
- defense_mechanisms（Character-LLM 心理防御轴）：提取人物最核心的自尊锚点与隐秘创伤雷区：
  * pride_anchors：人物绝不退让、赖以维持自尊的底线（如：自持读书人门第、文字书法技能），以及被贬低时的第一防御言行
  * trauma_triggers：容易引发强烈羞耻、防御或应激反应的创伤话题（如：科举未第、偷窃传闻、贫困被嘲），以及应激言行模式
- emotional_patterns 只收录情绪与心理模式（pattern_kind 为 stress/motivation/mood/self_talk）
- expression_dna 收录表达基因：这个人的说话方式。按以下维度逐一提取（有证据的维度才输出条目）：
  * 用词：口头禅（固定搭配）、高频词、领域黑话
  * 句式：平均句长（短句连发/长段落）、是否爱分点列条、结论位置（开门见山/先铺垫）、转折词频率
  * 标点与语气：标点习惯（句号/感叹号/省略号/波浪号）、语气词偏好（嗯/哦/哈哈/唉）、emoji 使用习惯
  * 称呼方式：怎么称呼对话者、怎么自称
  * 场景差异：情绪高低时的措辞差异、深夜与白天的表达差异、正式程度（1=极度正式 5=非常口语化）
  pattern_kind 为 expression 的实体归入此处；聊天记录与第一人称长文本（日记/信件/感想）都是证据来源——长文本可从句式节奏、反复出现的句型、自问自答习惯、标点风格、克制或铺陈的倾向中提取表达基因；example 尽量引用原文。没有证据就返回空数组，不要编造
- decision_patterns 收录决策模式：这个人怎么做决定。按以下维度提取（有证据的维度才输出条目）：
  * 风格：理性分析 vs 感觉驱动、纠结犹豫 vs 果断、提前计划 vs 随性、风险厌恶 vs 愿意冒险
  * 优先考量：做选择时最先权衡什么（效率/成本/人情/安全/自由/他人看法，按实际排序）
  * 触发：什么让TA真正动起来推进、什么让TA拖延回避或装作没看见
  * 反对方式：TA如何表达不同意（直接否定/提问质疑/沉默/转移话题）
  * 节奏与后悔：大决定与小决定的风格差异、做决定前会咨询谁、反复改变还是一锤定音、事后常后悔什么
  trait_kind 为 decision 的实体归入此处；日记与信件中记录的过往抉择（选了什么/放弃了什么/当时的挣扎）同样是决策证据。没有证据就返回空数组，不要编造
- 提取总则：区分证据与推断；优先提取可复现的模式而非生平概括；有原文依据的结论引用原话（加引号）
字段值缺失时用 null 或空串，不要删除字段。

图谱实体与事实如下：

{context}"""

STAGE2_PROMPT = """请合成以下叙事分区，输出紧凑精炼的 JSON：
{{
  "timeline": [{{"period": "时期", "kind": "education|work|project|life|gap", "summary": "简述（30字内）", "outcome": "结果", "source": ""}}],
  "milestones": [{{"milestone_kind": "turning_point|achievement|setback", "summary": "事件（30字内）", "impact": "影响（30字内）", "source": ""}}],
  "episodic_anchors": [
    {{
      "scene": "具象场景（如：鲁镇咸亨酒店柜台）",
      "involved_persons": ["主要关系人"],
      "core_conflict": "核心经历冲突（40字内）",
      "emotional_imprint": "情绪印记（30字内）",
      "cognitive_anchor": "铸就底层信念（30字内）",
      "source": ""
    }}
  ],
  "relationships": [{{"person": "姓名", "relation": "关系", "closeness": "close|regular|distant", "influence": "影响（30字内）", "source": ""}}],
  "aspirations": [{{"horizon": "short_term|mid_term|long_term", "polarity": "want|want_to_avoid", "content": "诉求（30字内）", "feasibility_note": "", "source": ""}}],
  "conflicts": [{{"field": "", "views": [""], "resolution": ""}}]
}}
分区说明：
- episodic_anchors（Character-LLM 经历剧场）：提取 2-3 个关键经历剧场，具备具体场景、冲突、情绪印记与长远认知影响，精炼表达
- 长度约束（严禁冗长，每项一两句话）：timeline 最多 4 条；milestones 最多 3 条；relationships 最多 4 位；aspirations 最多 3 条
- 时间线按时间正序排列；资料空白的时间段用 kind: "gap" 显式标注。字段值缺失时用 null 或空串，不要删除字段。
- 规范化目标（必须原样保留 goal_id 与 polarity，不得自行翻转）：{canonical_goals}

图谱实体与事实如下：

{context}"""

STAGE3_PROMPT = """基于前两阶段的画像分区，请做综合判断，输出 JSON：
{{
  "current_state": "一段综合判断（150字以内）：此人当前处于什么人生阶段、核心张力是什么、最重要的3个特征",
  "open_questions": ["资料缺口或值得补充的信息，最多5条"],
  "conflicts": [{{"field": "", "views": [""], "resolution": ""}}]
}}

阶段1（快照分区）：
{snapshot}

阶段2（叙事分区）：
{narrative}"""


def _validate_sources(data: Dict[str, Any], manifest: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Validate source labels and evidence references without failing the whole model."""
    warnings: List[str] = []
    manifest_map = {m.get("material_id"): m for m in (manifest or [])}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            source = value.get("source")
            refs = value.get("evidence_refs")
            if source and source != "inference":
                if source not in SOURCE_VALUES:
                    value["source"] = "inference"
                    warnings.append("invalid_source")
                elif not isinstance(refs, list) or not refs:
                    value["source"] = "inference"
                    value["traceability"] = "unverified"
                    warnings.append("missing_evidence_refs")
            if isinstance(refs, list):
                valid_refs = []
                for ref in refs:
                    if not isinstance(ref, dict):
                        continue
                    material = manifest_map.get(ref.get("material_id"))
                    chunk_id = ref.get("chunk_id")
                    span = ref.get("span") or {}
                    quote = ref.get("quote")
                    chunks = {c.get("chunk_id"): c for c in (material or {}).get("chunks", [])}
                    chunk = chunks.get(chunk_id)
                    ok = bool(material and chunk and isinstance(span, dict) and
                              isinstance(span.get("start"), int) and isinstance(span.get("end"), int) and
                              0 <= span["start"] <= span["end"] <= len(chunk.get("text", "")))
                    if ok and quote is not None:
                        actual = chunk["text"][span["start"]:span["end"]]
                        ok = " ".join(str(actual).split()) == " ".join(str(quote).split())
                    if ok:
                        valid_refs.append(ref)
                    else:
                        warnings.append("invalid_evidence_ref")
                value["evidence_refs"] = valid_refs
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return sorted(set(warnings))


def _extract_conflicts(*stages: Dict[str, Any]) -> List[Dict[str, Any]]:
    """汇总各阶段 conflicts 数组"""
    all_conflicts: List[Dict[str, Any]] = []
    for stage in stages:
        conflicts = stage.get("conflicts")
        if isinstance(conflicts, list):
            all_conflicts.extend(c for c in conflicts if isinstance(c, dict))
    return all_conflicts


class ProfileSynthesizer:
    """个人画像三阶段合成器"""

    def __init__(self, api_key: Optional[str] = None):
        self.llm = LLMClient(api_key=api_key) if api_key else LLMClient()
        self.reader = ZepEntityReader(api_key=Config.ZEP_API_KEY)

    def synthesize(
        self,
        graph_id: str,
        manifest: List[Dict[str, Any]],
        project_id: str,
        previous_version: int = 0,
        progress_callback=None,
        raw_text: Optional[str] = None,
        goals: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        执行三阶段合成，返回完整个人模型字典。

        Args:
            graph_id: Zep 图谱 ID
            manifest: 资料清单（用于 source_coverage）
            project_id: 项目 ID
            previous_version: 上一版本号（重建模时 +1）
            progress_callback: 可选 (stage, message) 回调
            raw_text: 材料合并原文（节选后供 Stage1 提取表达基因）
        """
        def report(stage: str, message: str):
            logger.info(f"[{graph_id}] {stage}: {message}")
            if progress_callback:
                progress_callback(stage, message)

        # 读取全量实体（带边富化）
        report("prepare", "读取图谱实体")
        filtered = self.reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=list(SNAPSHOT_TYPE_MAP) + list(NARRATIVE_TYPE_MAP),
            enrich_with_edges=True,
        )
        entities = filtered.entities
        if not entities:
            raise ValueError("图谱中未抽取到任何符合个人本体的实体，请检查资料质量")

        # 按分区分组
        snapshot_entities = [e for e in entities if e.get_entity_type() in SNAPSHOT_TYPE_MAP]
        narrative_entities = [e for e in entities if e.get_entity_type() in NARRATIVE_TYPE_MAP]

        # 系统提示词注入本项目实际存在的材料类型（source 标注约束）
        system_prompt = _build_system_prompt(manifest)
        evidence_context = _evidence_context(manifest)

        # 阶段1
        report("snapshot", f"合成快照分区（{len(snapshot_entities)} 个实体）")
        stage1 = _chat_json_with_retry(
            self.llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": STAGE1_PROMPT.format(
                    context=(
                        _stage1_context(
                            _entities_to_context(snapshot_entities or entities), raw_text,
                        )
                        + "\n\n可引用的证据索引（quote 必须逐字来自 text，并填写 span）：\n"
                        + evidence_context
                    )
                )},
            ],
            max_tokens=8192,
            progress_callback=progress_callback,
            stage="snapshot",
        )
        traceability_warnings = _backfill_evidence_refs(stage1, manifest)
        traceability_warnings.extend(_validate_sources(stage1, manifest))

        # 阶段2
        report("narrative", f"合成叙事分区（{len(narrative_entities)} 个实体）")
        stage2 = _chat_json_with_retry(
            self.llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": STAGE2_PROMPT.format(
                    context=(
                        _entities_to_context(narrative_entities or entities)
                        + "\n\n可引用的证据索引（quote 必须逐字来自 text，并填写 span）：\n"
                        + evidence_context
                    ),
                    canonical_goals=json.dumps(goals or [], ensure_ascii=False),
                )},
            ],
            max_tokens=8192,
            progress_callback=progress_callback,
            stage="narrative",
        )
        traceability_warnings.extend(_backfill_evidence_refs(stage2, manifest))
        traceability_warnings.extend(_validate_sources(stage2, manifest))

        # 阶段3
        report("synthesize", "综合判断")
        stage3 = _chat_json_with_retry(
            self.llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": STAGE3_PROMPT.format(
                    snapshot=json.dumps(
                        {k: v for k, v in stage1.items() if k != "conflicts"},
                        ensure_ascii=False,
                    ),
                    narrative=json.dumps(
                        {k: v for k, v in stage2.items() if k != "conflicts"},
                        ensure_ascii=False,
                    ),
                )},
            ],
            max_tokens=2048,
            progress_callback=progress_callback,
            stage="synthesize",
        )
        traceability_warnings.extend(_backfill_evidence_refs(stage3, manifest))
        traceability_warnings.extend(_validate_sources(stage3, manifest))

        # 合成最终模型
        report("finalize", "汇总个人模型")
        content_hash = hashlib.sha256(
            json.dumps(
                [e.to_dict() for e in entities], ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()[:16]

        model: Dict[str, Any] = {
            "model_version": previous_version + 1,
            "project_id": project_id,
            "graph_id": graph_id,
            "content_hash": content_hash,
            "created_at": datetime.now().isoformat(),
            "entity_count": len(entities),
        }
        # 快照分区（basic_info/personality/defense_mechanisms 为对象，其余为数组）
        for key in (
            "basic_info", "personality", "values", "skills", "interests",
            "emotional_patterns", "expression_dna", "decision_patterns", "defense_mechanisms",
        ):
            default = {} if key in ("basic_info", "personality", "defense_mechanisms") else []
            model[key] = stage1.get(key) or default
        # 叙事分区（Character-LLM 经历剧场）
        for key in ("timeline", "milestones", "relationships", "aspirations", "episodic_anchors"):
            model[key] = stage2.get(key) or []
        # 综合分区
        model["current_state"] = stage3.get("current_state", "")
        model["open_questions"] = stage3.get("open_questions", [])
        model["conflicts"] = _extract_conflicts(stage1, stage2, stage3)
        model["source_coverage"] = _manifest_source_summary(manifest)
        model["traceability"] = {
            "schema_version": 2,
            "warnings": sorted(set(traceability_warnings)),
            "verified": not traceability_warnings,
        }
        model["goals"] = goals or []

        report("finalize", f"个人模型 v{model['model_version']} 合成完成")
        return model
