"""
散文文风约束
化用 blader/humanizer（MIT，基于 Wikipedia "Signs of AI writing" 35 条模式）
按 PRISM 的三类散文场景裁剪为中文版：圆桌发言（口语）、人生推演叙事、主持人总评。

核心原则（humanizer 原版）：
1. 找出 AI 写作模式并消除
2. 保留每个事实主张，不编造细节
3. 写作样本优先于风格规则（voice matching）——PRISM 用 expression_dna 承担
4. 结合 Character-LLM 的具象经历锚点与心理防御机制，强化人设真实感与防漂移
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 圆桌发言文风（宇宙自我 / 关系人共享）
# 发言是口语，不是文章：真人说话有语塞、重复、跑题、节奏不均
# ---------------------------------------------------------------------------
SPEECH_STYLE_RULES = """文风铁律（像真人说话，不像 AI 写作）：
- 禁用 AI 高频腔：不用"值得注意的是""总而言之""在这个过程中""无疑""某种意义上""仿佛在诉说着"
- 禁用抬升式修辞：不说"标志着""开启了新篇章""人生的重要转折点""见证着""诠释了"
- 不用"不是X，而是Y"句式抖机灵；不用破折号（——）制造停顿感
- 不凑三段式排比（"勇气、智慧与坚韧"这种），要几个说几个
- 禁用格言式伪深刻收尾（"人生就是一场修行""选择比努力更重要"）——真人聊天不总结人生
- 句子长短不均：短句可以很短，长句可以磕绊；允许语塞、改口、话说一半
- 用具体代替抽象："又和领导吵了一架"好过"职场关系持续紧张"；细节（数字、地名、原话）优先于形容词"""

# ---------------------------------------------------------------------------
# 推演叙事文风（occurred_events / state_snapshot）
# 叙事要像纪录片旁白，不像宣传片
# ---------------------------------------------------------------------------
NARRATIVE_STYLE_RULES = """叙事文风铁律（像纪录片，不像宣传片）：
- 只写发生了什么：谁做了什么、说了什么、结果如何；不写"这彰显了""这反映了""这为将来埋下了伏笔"
- 禁用抬升式节点修辞："标志着""重要转折点""新的篇章""人生的新阶段"一律不用，里程碑就是事件本身
- 不编造抒情：state_snapshot 是状态快照，不是散文诗；不写"夜色中TA陷入了沉思"这类镜头感虚写
- 账面数字优先：能给出数字的（存款月数、健康分）直接给数字，不用"经济状况有所改善"这种模糊话
- 挫折写得平淡，成功也写得平淡；不渲染、不反转、不升华
- 每个 occurred_event 必须有可指认的行为主体（谁）和后果（怎样），不用无主句"""

# ---------------------------------------------------------------------------
# 主持人总评文风（summary 字段）
# ---------------------------------------------------------------------------
SUMMARY_STYLE_RULES = """summary 文风：一句话说清本轮圆桌的实质（最大分歧或最大收敛），平实直白；不用金句体收尾，不押韵，不排比。"""

# ---------------------------------------------------------------------------
# Voice matching（humanizer 的"写作样本优先"机制）
# 宇宙自我是"用户本人"在平行宇宙的投影，发言应匹配用户的表达基因
# ---------------------------------------------------------------------------

def voice_block(expression_dna: list) -> str:
    """
    把画像 expression_dna 分区渲染成发言文风约束块。
    无数据时返回空串（不注入，保持旧行为）。
    """
    if not expression_dna:
        return ""
    items = []
    for item in expression_dna:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature") or ""
        if not feature:
            continue
        example = item.get("example") or ""
        scene = item.get("scene") or ""
        line = f"- {feature}"
        if scene:
            line += f"（{scene}）"
        if example:
            line += f'；例："{example}"'
        items.append(line)
    if not items:
        return ""
    return "\n".join(["你说话要像TA本人（以下是从TA的真实聊天/日记中提取的表达基因，逐条遵循）："] + items)


def character_defense_block(defense_mechanisms: Optional[Dict[str, Any]]) -> str:
    """
    Character-LLM 心理防御与骄傲/创伤锚点渲染
    """
    if not defense_mechanisms or not isinstance(defense_mechanisms, dict):
        return ""
    lines = []
    prides = defense_mechanisms.get("pride_anchors") or []
    traumas = defense_mechanisms.get("trauma_triggers") or []
    
    if prides:
        lines.append("【骄傲与尊严底线（绝不退让，受侵犯时极易触发应激防御）】：")
        for p in prides:
            if isinstance(p, dict) and p.get("anchor"):
                lines.append(f"- 底线: {p['anchor']}（受挑战应激反应: {p.get('defense_behavior', '')}）")
                
    if traumas:
        lines.append("【敏感创伤/羞耻雷区（触及时情绪剧烈波动或闪躲回避）】：")
        for t in traumas:
            if isinstance(t, dict) and t.get("trigger"):
                lines.append(f"- 触发点: {t['trigger']}（应激言行模式: {t.get('response_pattern', '')}）")
                
    if not lines:
        return ""
    return "\n".join(["【心理防御机制（Character-LLM 角色防漂移锚点）】"] + lines)


def episodic_anchors_block(episodic_anchors: Optional[List[Dict[str, Any]]]) -> str:
    """
    Character-LLM 具象经历剧场渲染（锚定真实具象经历，抑制通用助手幻觉）
    """
    if not episodic_anchors or not isinstance(episodic_anchors, list):
        return ""
    lines = []
    for anchor in episodic_anchors:
        if not isinstance(anchor, dict) or not anchor.get("scene"):
            continue
        scene = anchor.get("scene", "")
        conflict = anchor.get("core_conflict", "")
        imprint = anchor.get("emotional_imprint", "")
        cog = anchor.get("cognitive_anchor", "")
        lines.append(f"- 场景: {scene} | 冲突: {conflict} | 情绪印记: {imprint} | 认知信念: {cog}")
        
    if not lines:
        return ""
    return "\n".join(["【关键经历剧场（塑造底层性格的具象经历，角色决策必须以此为心理根据）】"] + lines)
