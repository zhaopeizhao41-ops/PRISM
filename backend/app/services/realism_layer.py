"""
Realism Layer：人生推演引擎的真实性约束层。

独立的纯函数模块，三类核心能力：
  1. realism_state 初始化：从画像+关系卡+分支方向建立**持久化存量账本**
     （health / finance_ledger / relationships / windows / stress_carryover）
  2. 意外扰动生成器：每个阶段前按压力加权的概率抽取 life_event（好事/坏事）
     扰动直接改写账本并插入 occurred_events，LLM 不可控但必须产生后果
  3. 因果校验规则集：阶段推进后检测 4 维状态迁移是否违反常识
     （例：辞职→cash 不能涨；health<40→career 不能跃进）
     未通过则返回 violations 列表，供引擎要求 LLM 修正

账本字段均为小范围量化（0-100 或有序枚举），
保证 LLM 每次 advance 时面对的是"上阶段末的精确账面"而不是一句模糊的"经济稳定"。
"""

import hashlib
import json
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

# ---- 常量：意外事件池 ----
# 每条事件: (id, kind, weight, desc_template, effect_fn_key)
# effect_fn_key 对应 _EVENT_EFFECTS 中的函数，对 realism_state 产生侧写

_BAD_LUCK_POOL: List[Dict[str, Any]] = [
    {
        "id": "health_cold",
        "kind": "bad",
        "weight": 3,
        "template": "得了一场持续一周的流感，烧到 39 度，躺在床上什么都做不了。",
        "effect": {"health": -12, "career_hold": 1},
    },
    {
        "id": "finance_urgent_expense",
        "kind": "bad",
        "weight": 3,
        "template": "家里/个人发生一笔不可推迟的紧急支出（家电坏、修牙、家人医药费），花了 1-2 个月工资。",
        "effect": {"cash": -2, "debt": +1},
    },
    {
        "id": "relationship_quarrel",
        "kind": "bad",
        "weight": 3,
        "template": "和一个关系最近的人大吵了一架，谁也不肯先低头，冷战持续了两周。",
        "effect": {"tension_top": +18, "psyche_penalty": True},
    },
    {
        "id": "career_delay",
        "kind": "bad",
        "weight": 2,
        "template": "本来在推进的一件关键事被流程/他人放鸽子硬生生推迟了 1-2 个月。",
        "effect": {"career_hold": 2},
    },
    {
        "id": "health_chronic_flare",
        "kind": "bad",
        "weight": 1,
        "template": "老毛病突然发作（胃、腰、颈椎、失眠），白天精力只有平时的一半。",
        "effect": {"health": -8, "stress": +15},
    },
    {
        "id": "fraud_mistake",
        "kind": "bad",
        "weight": 1,
        "template": "被推销/熟人/平台坑了一笔不大的钱，或者签错了合同小亏一笔，想维权但没时间。",
        "effect": {"cash": -1},
    },
]

_GOOD_LUCK_POOL: List[Dict[str, Any]] = [
    {
        "id": "bonus_refund",
        "kind": "good",
        "weight": 3,
        "template": "意外收到一笔钱：年终奖比预期高、退税、旧债被归还，或一笔投资终于回本。",
        "effect": {"cash": +2},
    },
    {
        "id": "referral_opportunity",
        "kind": "good",
        "weight": 3,
        "template": "一个久未联系的朋友/前同事突然推荐了一个适合的机会：内推、合作、兼职。",
        "effect": {"opportunity": "referral", "stress": -8},
    },
    {
        "id": "relationship_reconciliation",
        "kind": "good",
        "weight": 2,
        "template": "和之前有矛盾的人在某个场景下自然和解，双方都松了一口气。",
        "effect": {"tension_top": -20, "psyche_bonus": True},
    },
    {
        "id": "health_recovery",
        "kind": "good",
        "weight": 2,
        "template": "坚持锻炼/调整作息了一段时间，身体明显比前一阶段更精神，睡眠也好了。",
        "effect": {"health": +10, "stress": -10},
    },
    {
        "id": "lucky_break",
        "kind": "good",
        "weight": 1,
        "template": "一个没想过的小概率好事发生了：抽中奖品、抢到票、遇到很聊得来的人。",
        "effect": {"psyche_bonus": True},
    },
]


def _pick_event(
    stress_carryover: int,
    stage_rand_seed: str,
    cash_months: int = 2,
    debt_months: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    按压力加权概率抽取意外事件。
    基础触发概率 = 15%，stress_carryover 每 10 点额外 +2%，上限 35%。
    好事/坏事比例：压力越高坏事越多（70:30 → stress>60 时 20:80）
    账本调节（P2-6）：现金缓冲 <=1 个月或债务 >=2 个月 → 坏事概率上调；
    现金缓冲 >=8 个月 → 坏事概率下调（家底厚扛得住）。
    """
    # 稳定随机：对 stage_rand_seed 哈希，保证同一阶段同一 session 重复调用结果一致
    seed = int(hashlib.sha256(stage_rand_seed.encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)

    base = 0.15 + min(0.20, (stress_carryover or 0) / 10 * 0.02)
    if rng.random() > base:
        return None

    # 决定好事 vs 坏事
    bad_ratio = 0.55 if (stress_carryover or 0) < 40 else (0.70 if (stress_carryover or 0) < 70 else 0.82)
    if cash_months is not None and cash_months <= 1:
        bad_ratio += 0.15  # 现金见底：坏运气更容易雪上加霜
    if (debt_months or 0) >= 2:
        bad_ratio += 0.08
    if cash_months is not None and cash_months >= 8:
        bad_ratio -= 0.10  # 家底厚：坏运气冲击有限
    bad_ratio = max(0.25, min(0.90, bad_ratio))
    is_bad = rng.random() < bad_ratio
    pool = _BAD_LUCK_POOL if is_bad else _GOOD_LUCK_POOL

    weights = [e["weight"] for e in pool]
    total = sum(weights)
    r = rng.random() * total
    acc = 0
    for event in pool:
        acc += event["weight"]
        if r <= acc:
            return dict(event)
    return dict(pool[-1])


def _apply_event_effect(state: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """把意外事件的 effect 应用到 realism_state。返回 delta 描述（给前端展示 + LLM 知晓）。"""
    effect = event.get("effect") or {}
    delta: Dict[str, Any] = {}

    # Health
    if "health" in effect:
        before = state.get("health_score", 80)
        state["health_score"] = max(0, min(100, before + effect["health"]))
        delta["health"] = effect["health"]

    # Finance: cash 是月数当量（3=三个月存款缓冲），debt 同级
    if "cash" in effect:
        before = state["finance_ledger"].get("cash_months", 2)
        state["finance_ledger"]["cash_months"] = max(0, before + effect["cash"])
        delta["cash_months"] = effect["cash"]
    if "debt" in effect:
        before = state["finance_ledger"].get("debt_months", 0)
        state["finance_ledger"]["debt_months"] = max(0, before + effect["debt"])
        delta["debt_months"] = effect["debt"]

    # Career hold：阻断本阶段 career 维度上升（在校验阶段实现惩罚，这里只标记）
    if effect.get("career_hold"):
        state["career_hold_stages"] = state.get("career_hold_stages", 0) + effect["career_hold"]
        delta["career_hold"] = effect["career_hold"]

    # Stress
    if "stress" in effect:
        before = state.get("stress_carryover", 20)
        state["stress_carryover"] = max(0, min(100, before + effect["stress"]))
        delta["stress"] = effect["stress"]
    # Psyche bonus/penalty -> 直接反馈到 stress 并在提示词中作为倾向
    if effect.get("psyche_bonus"):
        state["stress_carryover"] = max(0, state.get("stress_carryover", 20) - 10)
        delta["psyche"] = "+10"
    if effect.get("psyche_penalty"):
        state["stress_carryover"] = min(100, state.get("stress_carryover", 20) + 10)
        delta["psyche"] = "-10"

    # Relationship tension（top = 当前张力最高的那个关系）
    if "tension_top" in effect and state.get("relationships"):
        rels = sorted(state["relationships"], key=lambda r: r.get("tension", 0), reverse=True)
        target = rels[0]
        before = target.get("tension", 20)
        target["tension"] = max(0, min(100, before + effect["tension_top"]))
        target["last_event"] = event["template"][:30] + "…"
        delta["tension"] = {"with": target.get("name"), "delta": effect["tension_top"]}

    # Opportunity（注册一个临时窗口）
    if effect.get("opportunity"):
        state.setdefault("spontaneous_windows", []).append({
            "window_id": f"luck_{int(time.time()*1000)%100000}",
            "name": {
                "referral": "朋友推荐的机会",
            }.get(effect["opportunity"], effect["opportunity"]),
            "opens_at_stage": state.get("_current_stage", 1),
            "closes_at_stage": state.get("_current_stage", 1) + 1,  # 只在后续 1 个阶段内有效
            "taken": False,
            "source": "luck_event",
        })
        delta["opportunity"] = effect["opportunity"]

    return delta


# ---- 因果校验规则集 ----
# 每条规则：名字 + 判定函数 (prev_realism, prev_world_state, new_world_state) -> Optional[str] 违规描述
# 注意：规则要保守，宁可漏报也不要误杀（一误杀就要让 LLM 重跑，代价高）

def _rule_cash_drop_after_unemployment(prev_state, prev_ws, new_ws) -> Optional[str]:
    prev_career = (prev_ws or {}).get("career", "") or ""
    new_resources = (new_ws or {}).get("resources", "") or ""
    # 上一阶段 career 提到失业/裸辞/断收入，resources 不能出现存款充裕/经济变好
    if any(kw in prev_career for kw in ("失业", "裸辞", "离职", "断收入", "无收入")):
        if any(kw in new_resources for kw in ("存款", "充裕", "提升", "增长", "结余")):
            return "上一阶段 career 处于离职/断收入，resources 不应出现存款充裕/经济变好"
    return None


def _rule_career_improve_when_sick(prev_state, prev_ws, new_ws) -> Optional[str]:
    health = (prev_state or {}).get("health_score", 80)
    career_hold = (prev_state or {}).get("career_hold_stages", 0)
    new_career = (new_ws or {}).get("career", "") or ""
    if (health < 40 or career_hold > 0) and any(
        kw in new_career for kw in ("晋升", "突破", "高薪", "入职", "升迁", "飞跃", "大涨")
    ):
        return f"健康分{health}、career_hold={career_hold}，career 不应出现晋升/飞跃级提升"
    return None


def _rule_family_harmony_under_tension(prev_state, prev_ws, new_ws) -> Optional[str]:
    rels = (prev_state or {}).get("relationships") or []
    if not rels:
        return None
    max_tension = max(r.get("tension", 0) for r in rels)
    new_family = (new_ws or {}).get("family", "") or ""
    if max_tension >= 80 and any(kw in new_family for kw in ("和谐", "亲密", "美满", "温馨", "和睦")):
        return f"关系张力 {max_tension} 分，family 维度不应出现全句和谐/亲密类描述"
    return None


def _rule_psyche_jumpback(prev_state, prev_ws, new_ws) -> Optional[str]:
    prev_psyche = (prev_ws or {}).get("psyche", "") or ""
    new_psyche = (new_ws or {}).get("psyche", "") or ""
    stress = (prev_state or {}).get("stress_carryover", 20)
    # 上一阶段 psyche 崩溃级 + 压力高 + 没有提到治疗，不应直接变"自我接纳/平和"
    if stress >= 70 and any(kw in prev_psyche for kw in ("崩溃", "抑郁", "绝望", "无法入睡", "内耗严重")):
        if not any(kw in (prev_psyche + new_psyche) for kw in ("咨询", "治疗", "医生", "住院")):
            if any(kw in new_psyche for kw in ("平和", "自我接纳", "轻松", "释怀", "开悟")):
                return "压力 70+、无治疗记录，psyche 不应从崩溃直接跳至自我接纳"
    return None


def _rule_window_expired(prev_state, prev_ws, new_ws) -> Optional[str]:
    # 已关闭的窗口焦点，如果 new_world_state 说它成了，那是作弊
    for w in (prev_state or {}).get("windows", []) or []:
        if w.get("closes_at_stage") and (prev_state or {}).get("_current_stage", 1) > w["closes_at_stage"]:
            if not w.get("taken"):
                # 窗口名如"考公上岸""转行 XX"，如果在 career 里出现了关键动词就判
                keywords = [c for c in w.get("name", "") if len(c) > 1]
                for kw in keywords[:3]:
                    if kw and kw in ((new_ws or {}).get("career", "") or ""):
                        return f"窗口「{w.get('name')}」已经关闭且未取得，career 不应兑现它"
    return None


_CAUSAL_RULES = [
    _rule_cash_drop_after_unemployment,
    _rule_career_improve_when_sick,
    _rule_family_harmony_under_tension,
    _rule_psyche_jumpback,
    _rule_window_expired,
]


def check_causal_violations(
    prev_realism: Dict[str, Any],
    prev_world_state: Dict[str, Any],
    new_world_state: Dict[str, Any],
) -> List[str]:
    """返回违规描述列表（空 = 全通过）。"""
    violations: List[str] = []
    for rule in _CAUSAL_RULES:
        try:
            msg = rule(prev_realism, prev_world_state, new_world_state)
        except Exception:
            msg = None
        if msg:
            violations.append(msg)
    return violations


# ---- 账本初始化 ----

def _parse_age(basic: Dict[str, Any]) -> int:
    """从 basic_info 解析年龄：优先 age（int），其次 age_range（"45岁"/"30-35岁"→取中值），默认 30"""
    age = basic.get("age")
    if isinstance(age, int) and age > 0:
        return age
    text = str(basic.get("age_range") or "")
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if nums:
        return sum(nums) // len(nums)
    return 30


def _parse_cash_months(*texts: str) -> Optional[int]:
    """
    从材料文本解析"现金流仅够撑9个月"类描述 → 存款缓冲月数。
    匹配：撑/维持/够/仅够 + N + 个月；N个月的存款/现金/缓冲；存款/现金/缓冲 + N个月
    """
    combined = " ".join(t for t in texts if t)
    patterns = (
        r"(?:撑|撑过|维持|够|仅够|只够|烧)[^0-9]{0,8}(\d+)\s*(?:个|~|-)?\s*月",
        r"(\d+)\s*个月?(?:的)?(?:存款|现金|缓冲|储备|生活费)",
        r"(?:存款|现金|缓冲|储备)[^0-9]{0,8}(\d+)\s*个月",
    )
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return max(0, min(24, int(match.group(1))))
    return None


def init_realism_state(
    personal_model: Dict[str, Any],
    relationship_cards: Optional[List[Dict[str, Any]]],
    stage_plan: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    画像+关系卡+阶段计划 -> 初始 realism_state。
    返回可序列化 dict，作为 session['realism_state']。
    """
    basic = (personal_model or {}).get("basic_info") or {}
    resources_text = ((personal_model or {}).get("current_state") or "")
    psyche_conflicts = (personal_model or {}).get("conflicts") or []
    psyche_patterns = (personal_model or {}).get("emotional_patterns") or []

    def _as_text(v) -> str:
        if isinstance(v, list):
            parts = []
            for it in v:
                if isinstance(it, dict):
                    parts.append(str(it.get("content") or it.get("name") or it.get("trait") or it.get("pattern_kind") or ""))
                else:
                    parts.append(str(it))
            return " ".join(p for p in parts if p)
        return str(v or "")

    psyche_text = _as_text(psyche_conflicts) + " " + _as_text(psyche_patterns)
    resources_text = _as_text(resources_text)  # 兜底

    # ---- Finance 推断 ----
    # P0-2：优先从材料文本解析明确的"X个月"现金流数字（唯一可靠信号）
    basic_texts = " ".join(
        str(v) for v in (basic.get("financial_state"), basic.get("current_status")) if v
    )
    parsed_cash = _parse_cash_months(resources_text, basic_texts)

    resources_lower = resources_text.lower() + " " + basic_texts.lower()
    finance_known = False
    if parsed_cash is not None:
        finance_known = True
    if any(kw in resources_lower for kw in ("存款为零", "现金为零", "逾期", "多笔债务", "无收入")):
        cash_months, debt_months, income_stability = 0, 2, 1
        finance_known = True
    elif any(kw in resources_lower for kw in ("负债", "拮据", "啃老", "月光")):
        cash_months, debt_months, income_stability = 1, 1, 1
        finance_known = True
    elif any(kw in resources_lower for kw in ("稳定", "一般", "普通收入")):
        cash_months, debt_months, income_stability = 3, 0, 3
        finance_known = True
    elif any(kw in resources_lower for kw in ("充裕", "存款", "优渥", "高收入", "中产")):
        cash_months, debt_months, income_stability = 6, 0, 4
        finance_known = True
    else:
        cash_months, debt_months, income_stability = 2, 0, 2  # 默认：略紧
    if parsed_cash is not None:
        # 材料明确给出"现金流够撑 N 个月"：以材料为准
        cash_months = parsed_cash
        income_stability = max(1, min(5, 2 if parsed_cash <= 3 else 3))
        finance_known = True

    # ---- Health 推断 ----
    age = _parse_age(basic)
    stress_seed = 20
    if any(kw in psyche_text for kw in ("内耗", "失眠", "焦虑", "抑郁")):
        stress_seed += 30
    if any(kw in resources_lower for kw in ("失业", "负债", "亏损", "对赌")):
        stress_seed += 15
    age_penalty = max(0, (age - 30)) // 4
    health_score = max(10, min(100, 85 - stress_seed - age_penalty))

    # ---- Relationships（P0-1：关系卡 + 画像 relationships 合并，具体人名直通）----
    relationships: List[Dict[str, Any]] = []
    seen_names = set()

    def _tension_guess(description: str, base: int) -> int:
        if any(kw in description for kw in (
            "矛盾", "冲突", "反对", "不理解", "压", "恨", "怨", "冷战",
            "疏离", "疏远", "断裂", "离职", "失去诚信",
        )):
            base += 35
        elif any(kw in description for kw in ("支持", "亲密", "理解", "信任", "温暖")):
            base -= 10
        return max(0, min(100, base))

    # 1) 关系卡（relationship_agent_generator 产出的真实 schema：person_ref/relation_kind/persona...）
    for card in (relationship_cards or []):
        name = (card.get("name") or card.get("person_ref") or card.get("role") or "").strip()
        if not name or name in seen_names:
            continue
        desc_parts = [
            str(card.get("background") or ""),
            str(card.get("behavior_tendency") or ""),
            str(card.get("persona") or ""),
            str(card.get("core_concern") or ""),
            str(card.get("communication_style") or ""),
        ]
        known = card.get("known_positions") or []
        if isinstance(known, list):
            desc_parts.extend(
                str(p.get("stance") or "") for p in known if isinstance(p, dict)
            )
        description = " ".join(p for p in desc_parts if p)
        role = card.get("role") or card.get("relation_kind") or "关系人"
        relationships.append({
            "name": name,
            "role": role,
            "tension": _tension_guess(description, 20),
            "last_event": "（起点）",
        })
        seen_names.add(name)

    # 2) 画像 relationships（profile_synthesizer 产出：person/relation/closeness/influence）
    for rel in (personal_model or {}).get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        person = str(rel.get("person") or "").strip()
        if not person or person in seen_names:
            continue
        closeness = str(rel.get("closeness") or "")
        influence = str(rel.get("influence") or "")
        base_tension = {"distant": 45, "regular": 30, "close": 20}.get(closeness, 30)
        relationships.append({
            "name": person,
            "role": rel.get("relation") or "关系人",
            "tension": _tension_guess(influence, base_tension),
            "last_event": "（起点）",
        })
        seen_names.add(person)

    if not relationships:
        # 兜底：如果画像与关系卡都没有关系人，至少放一个"亲密的人"作为潜在摩擦来源
        relationships.append({
            "name": "身边最亲近的人",
            "role": "亲密关系",
            "tension": 30,
            "last_event": "（起点）",
        })

    # ---- Windows（从阶段计划提取：每个阶段焦点可能是一个窗口）----
    windows: List[Dict[str, Any]] = []
    for i, stage in enumerate(stage_plan):
        focus = stage.get("focus") or ""
        if any(kw in focus for kw in ("考试", "申请", "面试", "投", "上岸", "签约", "跳槽")):
            windows.append({
                "window_id": f"win_{i}",
                "name": focus[:16],
                "opens_at_stage": max(1, i + 1),
                "closes_at_stage": min(len(stage_plan), i + 2),
                "taken": False,
                "source": "stage_focus",
            })

    return {
        "health_score": health_score,
        "finance_ledger": {
            "cash_months": cash_months,
            "debt_months": debt_months,
            "income_stability": income_stability,  # 1 很不稳定 ~ 5 极稳定
            "known": finance_known,
            "source": "observed" if finance_known else "assumed",
        },
        "relationships": relationships,
        "windows": windows,
        "spontaneous_windows": [],
        "stress_carryover": stress_seed,
        "career_hold_stages": 0,
        "_current_stage": 1,  # 推进到第几阶段就写几，供窗口/校验判断
        "breaker_episodes": {},
    }


# ---- advance 前：注入 realism 块 + 抽取意外事件 ----
# 返回: (realism_block_text, life_event or None)
# 内部会直接修改 realism_state（副作用：life_event 效应 + career_hold 计数递减）

def prepare_stage_realism(
    realism_state: Dict[str, Any],
    session_id: str,
    stage_no: int,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    推进某阶段前调用：
      1. career_hold_stages 计数器减 1（本阶段不再受限时跳过）
      2. 概率抽取 life_event 并应用效果
      3. 返回给 ADVANCE_PROMPT 的 realism_block 文本
    """
    realism_state["_current_stage"] = stage_no

    # career_hold 衰减
    if realism_state.get("career_hold_stages", 0) > 0:
        realism_state["career_hold_stages"] -= 1

    # 抽意外事件（P2-6：财务账本状态参与概率调节）
    finance = realism_state["finance_ledger"]
    life_event = _pick_event(
        stress_carryover=realism_state.get("stress_carryover", 20),
        stage_rand_seed=f"{session_id}:{stage_no}:{int(time.time()//3600)}",
        cash_months=finance.get("cash_months", 2),
        debt_months=finance.get("debt_months", 0),
    )
    event_delta: Dict[str, Any] = {}
    if life_event:
        event_delta = _apply_event_effect(realism_state, life_event)

    # 组装 realism_block（纯文本给 LLM 读）
    finance = realism_state["finance_ledger"]
    rels_text_parts = []
    for r in realism_state.get("relationships", []):
        rels_text_parts.append(
            f"- {r['name']}（{r['role']}）关系张力 {r['tension']}/100，最近一次：{r.get('last_event', '—')}"
        )
    windows_parts = []
    for w in realism_state.get("windows", []) or []:
        status = "✓ 已取得" if w.get("taken") else (
            f"[{w.get('opens_at_stage', '?')}-{w.get('closes_at_stage', '?')}]阶段内有效，当前{stage_no}阶段"
            if w.get("closes_at_stage", 999) >= stage_no >= w.get("opens_at_stage", 0)
            else "已过期关闭"
        )
        windows_parts.append(f"- 窗口「{w.get('name')}」：{status}")
    for w in realism_state.get("spontaneous_windows", []) or []:
        status = "有效" if w.get("closes_at_stage", 0) >= stage_no else "已过期"
        windows_parts.append(f"- 临时机会「{w.get('name')}」：{status}（仅本阶段+下阶段内）")

    block_lines = [
        "【真实性约束层 · 上阶段末账面】",
        "（以下是本阶段的唯一事实来源：occurred_events 与 world_state 中涉及的钱、健康、关系、机会状态"
        "必须与账面数值一致；叙事中提及任何数字量级（存款/收入/时长）不得与账面矛盾，"
        "若叙事需要变化，变化必须通过本阶段发生的事件合理推导出来）",
        f"- 生理健康：{realism_state['health_score']}/100  {'（精力受限）' if realism_state['health_score'] < 50 else ''}",
        f"- 财务账本：存款≈{finance['cash_months']}个月缓冲，债务≈{finance['debt_months']}个月当量，收入稳定性 {finance['income_stability']}/5",
        f"- 压力残留：{realism_state.get('stress_carryover', 20)}/100",
        f"- 职业受限剩余：{realism_state.get('career_hold_stages', 0)} 阶段（本阶段 career 维度不应有上升性变化）" if realism_state.get(
            "career_hold_stages", 0) else "",
        "- 关系人张力账本：",
        *(rels_text_parts or ["  （无关系数据）"]),
        "- 机会窗口（过期即永久关闭，未取得视为错过）：",
        *(windows_parts or ["  （无）"]),
    ]
    if life_event:
        tag = "【坏运气】" if life_event.get("kind") == "bad" else "【好运气】"
        block_lines.append("")
        block_lines.append(f"{tag}本阶段的不可控事件（真实发生，必须在 occurred_events 中体现并对状态/账本产生真实连锁后果）：")
        block_lines.append(f"  * {life_event.get('template', '')}")
        if event_delta:
            block_lines.append(f"  * 对账面的直接影响：{json.dumps(event_delta, ensure_ascii=False)}")
        block_lines.append("  * 推演要求：不要把它写成'虚惊一场'或'被轻松化解'，把它当真实的外部约束。")

    # 关系人强制发声：把张力前 2 位作为强制发言目标
    top_tension = sorted(
        realism_state.get("relationships", []), key=lambda r: r.get("tension", 0), reverse=True
    )[:2]
    if top_tension:
        # 通用别称表：按关系名/角色精确匹配
        alias_map = {
            "伴侣": ["妻子", "老公", "丈夫", "配偶", "对象", "爱人", "TA", "ta", "他", "她", "身边人"],
            "亲密关系": ["伴侣", "妻子", "老公", "丈夫", "配偶", "对象", "爱人", "TA", "他", "她"],
            "身边最亲近的人": ["伴侣", "妻子", "老公", "丈夫", "对象", "家人", "爱人"],
            "父母": ["爸爸", "妈妈", "父亲", "母亲", "爸", "妈", "老爹", "老妈"],
            "父亲": ["爸爸", "老爹", "老爸", "爸"],
            "母亲": ["妈妈", "老妈", "母亲", "妈"],
            "朋友": ["哥们儿", "兄弟", "闺蜜", "好友", "老朋友", "朋友"],
            "同事": ["领导", "组长", "同事", "主任", "校长", "院长"],
        }
        # P0-1 动态别称：从关系人自己的 role 文本推导（覆盖"妻子""联合创始人""投资人"等具体关系）
        role_alias_rules = (
            ("妻子", ["妻子", "老婆", "爱人"]),
            ("老公", ["老公", "丈夫", "爱人"]),
            ("丈夫", ["丈夫", "老公", "爱人"]),
            ("配偶", ["配偶", "爱人", "伴侣"]),
            ("女儿", ["女儿", "孩子", "闺女"]),
            ("儿子", ["儿子", "孩子"]),
            ("母亲", ["妈妈", "母亲", "老妈"]),
            ("父亲", ["爸爸", "父亲", "老爸"]),
            ("创始", ["合伙人", "联合创始人", "老搭档"]),
            ("投资", ["投资人", "资方", "董事会"]),
            ("领导", ["领导", "老板", "上级"]),
        )

        def _aliases_for(rel: Dict[str, Any]) -> List[str]:
            # 1) 精确命中通用表
            for key, vals in alias_map.items():
                if key in rel.get("name", "") or rel.get("role", "") == key:
                    return list(vals)
            # 2) 从 role 文本动态推导
            role_text = f"{rel.get('name', '')} {rel.get('role', '')}"
            hits: List[str] = []
            for keyword, vals in role_alias_rules:
                if keyword in role_text:
                    hits.extend(v for v in vals if v not in hits)
            return hits

        block_lines.append("")
        block_lines.append("【关系人强制发声】本阶段以下 2 位必须在 occurred_events 中明确出现（"
                           "可用 TA 自己的真实称呼而非括号里的占位名），")
        block_lines.append("   说出自己的立场（支持/反对/犹豫/受伤/吃醋/疲惫），不允许全程沉默或无条件包容：")
        for r in top_tension:
            aliases = _aliases_for(r)
            extra = f"（在本阶段叙事中可以用以下任一称呼替换：{'/'.join(aliases)}）" if aliases else ""
            block_lines.append(
                f"  * 「{r['name']}」·{r['role']}（张力 {r['tension']}/100）{extra}："
                f"{ '倾向于制造摩擦或反对' if r['tension'] >= 50 else '倾向于支持但仍有自己的想法' }"
            )

    return "\n".join(line for line in block_lines if line != ""), life_event


# ---- 确定性真实感断路器状态机 (0 Token Circuit Breaker) ----

def check_circuit_breakers(
    realism_state: Dict[str, Any],
    stage_no: int,
    existing_forks: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    确定性真实感断路器（Deterministic Realism Circuit Breaker）：
    零 Token 消耗、微秒级执行的代码断言拦截。
    
    检测三大致命生存危机：
    1. 破产断路器 (Insolvency)：现金储备归零且债务积压 (cash_months <= 0 and debt_months >= 2)
    2. 健康崩塌断路器 (Health Collapse)：健康评分跌破 40 (health_score < 40)
    3. 关系反目断路器 (Tension Explosion)：与任意关键关系人张力 >= 80
    
    若命中且尚未在该阶段被裁决，直接返回结构化强制分叉对象，拦截推演进行。
    """
    episodes = realism_state.setdefault("breaker_episodes", {})

    # Hysteresis: an acknowledged episode is closed only after the ledger has
    # crossed a safer threshold, allowing a later relapse to open a new one.
    finance_now = realism_state.get("finance_ledger", {})
    if (episodes.get("insolvency") or {}).get("status") == "acknowledged":
        if finance_now.get("cash_months", 0) >= 1 and finance_now.get("debt_months", 0) <= 1:
            episodes["insolvency"]["status"] = "recovered"
    if (episodes.get("health") or {}).get("status") == "acknowledged":
        if realism_state.get("health_score", 0) >= 60:
            episodes["health"]["status"] = "recovered"
    for key, episode in list(episodes.items()):
        if not key.startswith("tension_") or episode.get("status") != "acknowledged":
            continue
        person = key[len("tension_"):]
        rel = next((r for r in realism_state.get("relationships", []) if r.get("name") == person), None)
        if rel and rel.get("tension", 0) <= 50:
            episode["status"] = "recovered"

    def active(key: str) -> bool:
        return (episodes.get(key) or {}).get("status") in {"open", "acknowledged"}

    def mark(key: str, fork: Dict[str, Any]) -> Dict[str, Any]:
        state = episodes.setdefault(key, {})
        state.setdefault("episode_id", f"br_{key}_{stage_no}")
        state.setdefault("opened_stage", stage_no)
        state["last_seen_stage"] = stage_no
        state["status"] = "open"
        fork["breaker_key"] = key
        fork["episode_id"] = state["episode_id"]
        return fork

    # 1. 破产断路器
    finance = realism_state.get("finance_ledger", {})
    cash_months = finance.get("cash_months")
    debt_months = finance.get("debt_months")
    if finance.get("known", True) and cash_months is not None and debt_months is not None and cash_months <= 0 and debt_months >= 2 and not active("insolvency"):
        return mark("insolvency", {
            "fork_id": f"circuit_insolvency_{stage_no}",
            "at_stage": stage_no,
            "circuit_breaker": "insolvency",
            "is_emergency": True,
            "question": "【真实感断路器 · 资金链断裂】现金储备已彻底归零且面临多笔债务上门逼迫，基本温饱受到严重威胁。你选择如何应对这次致命财务危机？",
            "options": [
                {
                    "label": "抵押仅存栖身之所 / 变卖最后随身家当",
                    "condition": "变卖全部剩余资产勉强冲抵部分旧债，生活条件跌入绝境，但争取到 1-2 个月喘息期",
                    "effects": {"finance": {"cash_months_delta": 1, "debt_months_delta": -1}, "stress_delta": 5}
                },
                {
                    "label": "向债主低头屈从 / 接受高息苛刻劳役偿债",
                    "condition": "向掌柜或放贷方立下严苛字据，心理承压与关系张力飙升至极点，以失去自由为代价维持生计",
                    "effects": {"finance": {"cash_months_delta": 1, "debt_months_delta": -1}, "stress_delta": 15}
                }
            ],
            "resolved": None,
        })

    # 2. 健康崩塌断路器
    health_score = realism_state.get("health_score", 80)
    if health_score < 40 and not active("health"):
        return mark("health", {
            "fork_id": f"circuit_health_{stage_no}",
            "at_stage": stage_no,
            "circuit_breaker": "health",
            "is_emergency": True,
            "question": f"【真实感断路器 · 身体机能崩塌】健康评分降至 {health_score}/100（重度透支/重病未愈），剧烈病痛导致无法承担常规劳作。你如何抉择？",
            "options": [
                {
                    "label": "散尽仅有盘缠彻底停工就医抓药",
                    "condition": "暂停一切生计彻底卧床休养，资金耗尽甚至不得不举债求医，换取体能逐步脱离危险期",
                    "effects": {"health_delta": 25, "cash_months_delta": -1, "stress_delta": -10}
                },
                {
                    "label": "咬紧牙关带病强行出工硬扛",
                    "condition": "拒绝停工强忍剧痛继续劳作，短期勉强维持微薄进项，但落下严重终身不可逆损伤",
                    "effects": {"health_delta": -10, "cash_months_delta": 1, "stress_delta": 10}
                }
            ],
            "resolved": None,
        })

    # 3. 关系反目断路器
    for rel in realism_state.get("relationships", []):
        tension = rel.get("tension", 0)
        name = rel.get("name", "关键关系人")
        key = f"tension_{name}"
        if tension >= 80 and not active(key):
            return mark(key, {
                "fork_id": f"circuit_tension_{name}_{stage_no}",
                "at_stage": stage_no,
                "circuit_breaker": f"tension_{name}",
                "is_emergency": True,
                "question": f"【真实感断路器 · 人际关系反目】与「{name}」的矛盾张力突破临界值（{tension}/100）。对方上门公开质问对质，你如何表态？",
                "options": [
                    {
                        "label": f"当面低头服软，全盘接受「{name}」的苛刻要求",
                        "condition": f"彻底放弃个人原则向「{name}」认错退让，换取关系张力暂时缓和，但自尊与利益受重创",
                        "effects": {"relationship": {"person": name, "tension_delta": -35}, "stress_delta": 5}
                    },
                    {
                        "label": f"正面激烈摊牌对质，彻底决裂断交",
                        "condition": f"与「{name}」公开撕破脸皮决裂，承受其在圈子内的排挤与封杀，人际张力锁定在最高点",
                        "effects": {"relationship": {"person": name, "tension_delta": 20, "status": "severed"}, "stress_delta": 10}
                    }
                ],
                "resolved": None,
            })

    return None
