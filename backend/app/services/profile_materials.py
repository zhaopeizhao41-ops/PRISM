"""
个人画像层资料预处理
职责：
1. 结构化表单（量化基础信息）→ 带来源标注的文本块
2. 自由资料（粘贴文本/文件）→ 带来源标注的文本块
3. 多源文本合并为单一 ingestion 输入
4. 聊天记录材料解析增强（区分我方发言、场景标签、表达统计）

设计文档见 docs/PERSONAL_PROFILE_DESIGN.md 第二节/第四节。
"""

import hashlib
import re
from typing import Any, Dict, List, Optional

# 可信度权重表（与设计文档 2.3 节一致，前后端共用约定）
MATERIAL_CONFIDENCE = {
    "structured_form": 0.95,
    "resume": 0.85,
    "chat_log": 0.70,
    "diary": 0.60,
    "reflection": 0.55,
    "preference": 0.40,
    "other": 0.40,
    "literary": 0.35,
}

VALID_MATERIAL_TYPES = set(MATERIAL_CONFIDENCE.keys())
VALID_MATERIAL_MODES = {"personal", "fictional"}
MATERIAL_TYPE_ALIASES = {"fictional": "literary", "novel": "literary"}

# 表单分区 → 字段清单（用于归一化渲染，顺序即输出顺序）
_BASIC_FIELDS = [
    ("nickname", "称呼"),
    ("age_range", "年龄段"),
    ("gender", "性别"),
    ("location", "城市"),
    ("industry", "行业/职业方向"),
    ("current_status", "当前状态"),
    ("education_level", "学历阶段"),
    ("financial_state", "财务状态"),
]

_PERSONALITY_FIELDS = [
    ("mbti", "MBTI"),
    ("self_tags", "自我描述标签"),
]

_RELATION_FIELDS = [
    ("family_status", "家庭状态"),
    ("social_support", "社交支持度"),
]

_GOAL_FIELDS = [
    ("goal_short_term", "近1-3年最想实现的事"),
    ("current_blocker", "当前最大的卡点"),
    ("want_to_avoid", "明确不想要的"),
]


def _clean(value: Any) -> Optional[str]:
    """None / 空串 / 空白 / 占位值统一归为 None"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"n/a", "na", "null", "none", "不便透露", "不确定", "prefer not to say", "unknown"}:
            return None
        return text
    return str(value)


def _render_section(title: str, pairs: List[tuple]) -> str:
    """渲染一个表单分区：只包含已填写字段"""
    filled = [(label, cleaned) for label, cleaned in pairs if cleaned]
    if not filled:
        return ""
    body = "; ".join(f"{label}: {value}" for label, value in filled)
    return f"【{title}】{body}"


def _render_skills(skills: List[Dict[str, Any]]) -> str:
    items = []
    for skill in skills or []:
        name = _clean(skill.get("name"))
        if not name:
            continue
        level = _clean(skill.get("proficiency")) or "?"
        domain = _clean(skill.get("domain")) or "专业"
        items.append(f"{name}({level},{domain})")
    return "; ".join(items) if items else ""


def _render_relations(relations: List[Dict[str, Any]]) -> str:
    items = []
    for rel in relations or []:
        person = _clean(rel.get("person"))
        if not person:
            continue
        relation = _clean(rel.get("relation")) or "其他"
        closeness = _clean(rel.get("closeness")) or "?"
        influence = _clean(rel.get("influence")) or ""
        item = f"{person}({relation},亲密度{closeness}"
        if influence:
            item += f',"{influence}"'
        item += ")"
        items.append(item)
    return "; ".join(items) if items else ""


def _render_big5(big5: Dict[str, Any]) -> str:
    if not isinstance(big5, dict):
        return ""
    keys = [("openness", "开放性"), ("conscientiousness", "尽责性"),
            ("extraversion", "外向性"), ("agreeableness", "宜人性"),
            ("neuroticism", "神经质")]
    pairs = []
    for key, label in keys:
        value = big5.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        try:
            pairs.append(f"{label}{int(value)}")
        except (TypeError, ValueError):
            continue
    return " ".join(pairs) if pairs else ""


def structured_form_to_text(form: Dict[str, Any]) -> str:
    """
    结构化表单 → 带来源头的文本块。
    全部字段可选：只渲染已填写部分，全空表单返回空串。
    """
    if not isinstance(form, dict):
        return ""

    lines: List[str] = []

    basic = _render_section(
        "基本盘", [(label, _clean(form.get(key))) for key, label in _BASIC_FIELDS]
    )
    if basic:
        lines.append(basic)

    personality_parts = []
    big5_text = _render_big5(form.get("big5"))
    for key, label in _PERSONALITY_FIELDS:
        value = form.get(key)
        if key == "self_tags" and isinstance(value, list):
            tags = ", ".join(v for v in (_clean(t) for t in value) if v)
            if tags:
                personality_parts.append(f"标签: {tags}")
        else:
            cleaned = _clean(value)
            if cleaned:
                personality_parts.append(f"{label}: {cleaned}")
    if big5_text:
        personality_parts.append(f"大五: {big5_text}")
    if personality_parts:
        lines.append("【性格与认知】" + "; ".join(personality_parts))

    skills_text = _render_skills(form.get("skills"))
    if skills_text:
        lines.append(f"【能力与资源】技能: {skills_text}")

    relation_parts = []
    for key, label in _RELATION_FIELDS:
        cleaned = _clean(form.get(key))
        if cleaned:
            relation_parts.append(f"{label}: {cleaned}")
    relations_text = _render_relations(form.get("important_relations"))
    if relations_text:
        relation_parts.append(f"重要关系人: {relations_text}")
    if relation_parts:
        lines.append("【人际与支持】" + "; ".join(relation_parts))

    goals = _render_section(
        "目标与困扰", [(label, _clean(form.get(key))) for key, label in _GOAL_FIELDS]
    )
    if goals:
        lines.append(goals)

    if not lines:
        return ""

    header = (
        f"=== [结构化输入 | 来源: 量化表单 | 置信度: "
        f"{MATERIAL_CONFIDENCE['structured_form']}] ==="
    )
    return header + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# 聊天记录解析增强（化用 yourself-skill wechat_parser 思路）
# 聊天记录不再是整段直通图谱，而是附加一份自动解析摘要：
# 区分我方发言、打场景标签（决策类/情绪类/深夜）、统计表达习惯，
# 直接服务 expression_dna 与 decision_patterns 两个画像分区的证据供给。
# ---------------------------------------------------------------------------

# WeChatMsg 导出格式："2024-01-15 20:30:45 张三"，也兼容 "张三 2024-01-15 20:30"
_CHAT_MSG_PATTERN = re.compile(
    r'^(?:(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+([^\s|]+)'
    r'|([^\s|]+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}(?::\d{2})?))$'
)

_SELF_SENDERS = {"我", "me", "i", "self", "本人"}

_DECISION_KEYWORDS = re.compile(
    r"决定|选择|要不要|该不该|纠结|犹豫|offer|辞职|跳槽|考研|考公|分手|复合|"
    r"选哪个|怎么办|还是|转行|买房|搬家|告白|表白|拒绝|接受|答应"
)
_EMOTION_KEYWORDS = re.compile(
    r"累|烦|开心|难过|焦虑|崩溃|高兴|生气|委屈|孤独|害怕|兴奋|沮丧|压力|"
    r"emo|失眠|睡不着|心累|想哭|舒服|满足|失望|心疼|讨厌|喜欢"
)

_PARTICLE_PATTERN = re.compile(r"[哈嗯哦噢嘿唉呜啊呀吧嘛呢吗么嘿]+")
_LATE_NIGHT_HOURS = set(range(0, 6)) | {23}

_MAX_SAMPLES_PER_SCENE = 15


def _parse_chat_messages(text: str) -> List[Dict[str, Any]]:
    """
    解析聊天记录为消息列表（timestamp/sender/content/hour）。
    不匹配消息头格式的行归属上一条消息；无任何消息头时返回空列表。
    """
    messages = []
    current = None
    for line in text.splitlines():
        match = _CHAT_MSG_PATTERN.match(line.strip())
        if match:
            if current:
                messages.append(current)
            if match.group(1):  # 时间在前
                date, time_str, sender = match.group(1), match.group(2), match.group(3)
            else:  # 发送者在前
                sender, date, time_str = match.group(4), match.group(5), match.group(6)
            try:
                hour = int(time_str.split(":")[0])
            except (ValueError, IndexError):
                hour = None
            current = {
                "timestamp": f"{date} {time_str}",
                "sender": sender.strip(),
                "content": "",
                "hour": hour,
            }
        elif current is not None and line.strip():
            if current["content"]:
                current["content"] += "\n" + line.rstrip()
            else:
                current["content"] = line.rstrip()
    if current:
        messages.append(current)
    return messages


def _scene_of(msg: Dict[str, Any]) -> Optional[str]:
    """给单条消息打场景标签：decision / emotion / late_night（可叠加情绪）"""
    content = msg.get("content", "")
    if not content:
        return None
    if _DECISION_KEYWORDS.search(content):
        return "decision"
    if _EMOTION_KEYWORDS.search(content):
        return "emotion"
    return "chat"


def _expression_stats(texts: List[str]) -> str:
    """统计我方发言的表达习惯（ yourself-skill analyze_messages 的轻量版）"""
    joined = " ".join(texts)
    lengths = [len(t) for t in texts if t]
    avg = round(sum(lengths) / len(lengths), 1) if lengths else 0
    style = "短句连发型" if avg < 20 else "长段落型"

    particles = _PARTICLE_PATTERN.findall(joined)
    particle_freq: Dict[str, int] = {}
    for p in particles:
        particle_freq[p] = particle_freq.get(p, 0) + 1
    top_particles = sorted(particle_freq.items(), key=lambda x: -x[1])[:5]
    particle_text = "、".join(f"{w}({c})" for w, c in top_particles) if top_particles else "无明显语气词"

    punct = {
        "感叹号": joined.count("！") + joined.count("!"),
        "问号": joined.count("？") + joined.count("?"),
        "省略号": joined.count("...") + joined.count("…"),
        "波浪号": joined.count("～") + joined.count("~"),
    }
    punct_text = "、".join(f"{k}{v}次" for k, v in punct.items())
    return f"平均长度{avg}字（{style}）；高频语气词: {particle_text}；标点: {punct_text}"


def enhance_chat_log(text: str) -> str:
    """
    聊天记录解析增强入口：
    - 识别为聊天记录（≥5 条消息头）时，附加解析摘要（我方发言、场景标签、表达统计）
    - 识别不出消息结构时原样返回（保持旧行为）
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned

    messages = _parse_chat_messages(cleaned)
    if len(messages) < 5:
        return cleaned

    self_msgs = [m for m in messages if m["sender"].lower() in _SELF_SENDERS]
    lines = ["--- 聊天记录解析摘要（自动生成，供画像提取参考）---"]
    lines.append(f"消息总数: {len(messages)}")

    if not self_msgs:
        lines.append(
            '我方发言识别: 未能识别（发送者名称均不含"我"），以下统计基于全部消息；'
            "图谱提取时请注意区分说话人"
        )
        target_msgs = messages
    else:
        lines.append(f'我方发言识别: {len(self_msgs)}条（发送者名为"我"）')
        target_msgs = self_msgs

    # 场景标签统计（深夜作为独立维度叠加统计）
    scene_counts = {"decision": 0, "emotion": 0, "chat": 0}
    late_night_count = 0
    samples: Dict[str, List[str]] = {"decision": [], "emotion": []}
    for msg in target_msgs:
        scene = _scene_of(msg)
        if scene:
            scene_counts[scene] += 1
        if msg.get("hour") in _LATE_NIGHT_HOURS and msg["content"]:
            late_night_count += 1
        if scene in samples and len(samples[scene]) < _MAX_SAMPLES_PER_SCENE:
            samples[scene].append(msg["content"].replace("\n", " "))

    lines.append(
        f"场景分布: 决策相关{scene_counts['decision']}条、"
        f"情绪表达{scene_counts['emotion']}条、"
        f"闲聊{scene_counts['chat']}条（其中深夜时段{late_night_count}条）"
    )
    if target_msgs:
        lines.append(f"表达统计: {_expression_stats([m['content'] for m in target_msgs])}")

    for label, key in (("我方决策类发言样本", "decision"), ("我方情绪类发言样本", "emotion")):
        if samples[key]:
            lines.append(f"{label}:")
            for i, sample in enumerate(samples[key], 1):
                lines.append(f"{i}. {sample}")

    return cleaned + "\n\n" + "\n".join(lines)


def free_material_to_text(
    text: str,
    material_type: str,
    time_range: Optional[str] = None,
    material_mode: str = "personal",
) -> str:
    """
    自由资料（粘贴文本或文件提取文本）→ 带来源头的文本块。
    material_type 必须是 MATERIAL_CONFIDENCE 中的键。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    material_type = MATERIAL_TYPE_ALIASES.get(material_type, material_type)
    if material_type not in VALID_MATERIAL_TYPES:
        material_type = "other"
    if material_mode not in VALID_MATERIAL_MODES:
        material_mode = "personal"

    # 聊天记录解析增强：附加自动解析摘要（我方发言/场景标签/表达统计）
    if material_type == "chat_log":
        cleaned = enhance_chat_log(cleaned)

    mode_part = f" | 模式: {material_mode}" if material_mode == "fictional" else ""
    parts = [f"=== [{material_type}{mode_part} | 来源: 用户提交"]
    if time_range and time_range.strip():
        parts.append(f" | 时间范围: {time_range.strip()}")
    parts.append(f" | 置信度: {MATERIAL_CONFIDENCE[material_type]}] ===")
    return "\n".join(["".join(parts), cleaned])


def merge_materials(blocks: List[str]) -> str:
    """合并多个文本块为单一 ingestion 输入（保持顺序，块间空行分隔）"""
    return "\n\n".join(block for block in blocks if block and block.strip())


def material_fingerprint(text: str) -> str:
    """资料指纹（sha256 前 16 位），用于 materials_manifest 去重"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def canonicalize_goals(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert legacy goal fields into a stable, polarity-preserving contract."""
    if not isinstance(form, dict):
        return []
    goals: List[Dict[str, Any]] = []
    explicit = form.get("goals")
    if isinstance(explicit, list):
        for index, item in enumerate(explicit):
            if not isinstance(item, dict):
                continue
            content = _clean(item.get("content") or item.get("text"))
            if not content:
                continue
            polarity = item.get("polarity")
            if polarity not in {"want", "want_to_avoid"}:
                polarity = "unknown"
            goals.append({
                "goal_id": str(item.get("goal_id") or f"goal_{index + 1}"),
                "horizon": _clean(item.get("horizon")) or "short_term",
                "content": content,
                "polarity": polarity,
                "legacy": bool(item.get("legacy")),
            })
    legacy_pairs = (
        ("goal_short_term", "want", "short_term"),
        ("want_to_avoid", "want_to_avoid", "short_term"),
    )
    for key, polarity, horizon in legacy_pairs:
        content = _clean(form.get(key))
        if content and not any(g["content"] == content for g in goals):
            goals.append({
                "goal_id": f"goal_{len(goals) + 1}",
                "horizon": horizon,
                "content": content,
                "polarity": polarity,
                "legacy": True,
            })
    return goals


def build_evidence_index(material_id: str, text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, Any]]:
    """Create deterministic, locally verifiable evidence chunks for a material."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    chunk_size = max(1, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size - 1))
    step = chunk_size - overlap
    chunks: List[Dict[str, Any]] = []
    for ordinal, start in enumerate(range(0, len(cleaned), step)):
        end = min(len(cleaned), start + chunk_size)
        chunk_text = cleaned[start:end]
        chunks.append({
            "chunk_id": f"{material_id}:c{ordinal}",
            "ordinal": ordinal,
            "start": start,
            "end": end,
            "text": chunk_text,
            "text_sha256": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
        })
        if end >= len(cleaned):
            break
    return chunks


def count_filled_fields(form: Dict[str, Any]) -> int:
    """统计表单中已填写的顶层字段数（用于 /structured-input 响应）"""
    if not isinstance(form, dict):
        return 0
    count = 0
    for key in form:
        if key in {"big5", "skills", "important_relations", "self_tags"}:
            continue
        if _clean(form.get(key)):
            count += 1
    if _render_big5(form.get("big5")):
        count += 1
    if _render_skills(form.get("skills")):
        count += 1
    if _render_relations(form.get("important_relations")):
        count += 1
    if any(_clean(t) for t in (form.get("self_tags") or []) if isinstance(t, str)):
        count += 1
    return count
