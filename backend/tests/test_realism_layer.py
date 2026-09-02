"""Realism Layer 单元测试：纯函数模块，不依赖 LLM。"""

import pytest

from app.services.realism_layer import (
    _apply_event_effect,
    _parse_age,
    _parse_cash_months,
    _pick_event,
    check_causal_violations,
    init_realism_state,
    prepare_stage_realism,
)


# ---------- _parse_age ----------

def test_parse_age_prefers_int():
    assert _parse_age({"age": 45}) == 45


def test_parse_age_from_range_takes_average():
    assert _parse_age({"age_range": "30-35岁"}) == 32


def test_parse_age_defaults_to_30():
    assert _parse_age({}) == 30


# ---------- _parse_cash_months ----------

def test_parse_cash_months_survive_pattern():
    assert _parse_cash_months("现金流仅够撑9个月") == 9
    assert _parse_cash_months("存款大概能维持 12 个月") == 12


def test_parse_cash_months_deposit_pattern():
    assert _parse_cash_months("有3个月的存款") == 3
    assert _parse_cash_months("现金缓冲 5 个月") == 5


def test_parse_cash_months_none_when_absent():
    assert _parse_cash_months("他过着普通的生活") is None


# ---------- init_realism_state ----------

def _minimal_model(**overrides):
    model = {
        "basic_info": {"age": 35},
        "current_state": "在一家公司做工程师",
        "conflicts": [],
        "emotional_patterns": [],
    }
    model.update(overrides)
    return model


def test_init_realism_state_defaults():
    state = init_realism_state(_minimal_model(), [], [{"stage_label": "阶段1", "focus": "适应"}])
    assert 10 <= state["health_score"] <= 100
    assert state["finance_ledger"]["cash_months"] == 2  # 默认略紧
    assert state["stress_carryover"] >= 20
    assert state["career_hold_stages"] == 0
    assert state["_current_stage"] == 1
    # 无关系数据时兜底一个关系人
    assert len(state["relationships"]) == 1
    assert state["relationships"][0]["name"] == "身边最亲近的人"


def test_init_realism_state_merges_relationship_sources():
    model = _minimal_model(relationships=[
        {"person": "老陈", "relation": "前合伙人", "closeness": "distant", "influence": "关系紧张"},
        {"person": "宋婉", "relation": "妻子", "closeness": "close", "influence": "互相支持"},
    ])
    cards = [
        {"person_ref": "老陈", "relation_kind": "前合伙人", "background": "合作多年后闹翻"},
        {"person_ref": "周小雨", "relation_kind": "下属", "background": "信任"},
    ]
    state = init_realism_state(model, cards, [{"stage_label": "阶段1", "focus": "启动"}])
    names = [r["name"] for r in state["relationships"]]
    # 关系卡先入账，画像 relationships 去重后合并
    assert names == ["老陈", "周小雨", "宋婉"]
    # 老陈描述含冲突关键词 → 张力上调；宋婉含支持 → 张力下调
    tension = {r["name"]: r["tension"] for r in state["relationships"]}
    assert tension["老陈"] > tension["宋婉"]


def test_init_realism_state_finance_keywords():
    poor = init_realism_state(_minimal_model(current_state="负债累累，存款为零"), [], [])
    rich = init_realism_state(_minimal_model(current_state="存款充裕，生活优渥"), [], [])
    assert poor["finance_ledger"]["cash_months"] == 0
    assert poor["finance_ledger"]["debt_months"] == 2
    assert rich["finance_ledger"]["cash_months"] == 6
    assert rich["finance_ledger"]["debt_months"] == 0


def test_init_realism_state_explicit_cash_overrides_keywords():
    model = _minimal_model(current_state="现金流仅够撑9个月")
    state = init_realism_state(model, [], [])
    # 材料明确数字优先于关键词推断（"个月"不会触发任何关键词档位）
    assert state["finance_ledger"]["cash_months"] == 9


def test_init_realism_state_psychology_raises_stress():
    calm = init_realism_state(_minimal_model(), [], [])
    anxious = init_realism_state(
        _minimal_model(conflicts=[{"content": "长期内耗与失眠"}]), [], []
    )
    assert anxious["stress_carryover"] > calm["stress_carryover"]
    assert anxious["health_score"] < calm["health_score"]


def test_init_realism_state_extracts_windows_from_stage_plan():
    plan = [
        {"stage_label": "阶段1", "focus": "备考公务员考试"},
        {"stage_label": "阶段2", "focus": "日常运营"},
    ]
    state = init_realism_state(_minimal_model(), [], plan)
    assert len(state["windows"]) == 1
    win = state["windows"][0]
    assert win["name"].startswith("备考公务员考试")
    assert win["taken"] is False
    assert win["opens_at_stage"] == 1
    assert win["closes_at_stage"] == 2


# ---------- _pick_event ----------

def test_pick_event_is_deterministic_per_seed():
    args = dict(stress_carryover=50, stage_rand_seed="session-1:stage-2")
    first = _pick_event(**args)
    second = _pick_event(**args)
    assert first == second


def test_pick_event_returns_none_or_valid_event():
    # 扫描多个种子，验证返回值结构合法
    for i in range(50):
        event = _pick_event(stress_carryover=30, stage_rand_seed=f"s:{i}")
        if event is None:
            continue
        assert event["kind"] in ("good", "bad")
        assert event["id"] and event["template"]
        assert isinstance(event["effect"], dict)
        return
    pytest.fail("50 个种子全部返回 None，基础触发概率疑似配置错误")


# ---------- _apply_event_effect ----------

def _base_state():
    return {
        "health_score": 50,
        "finance_ledger": {"cash_months": 3, "debt_months": 0, "income_stability": 3},
        "relationships": [
            {"name": "甲", "role": "朋友", "tension": 20, "last_event": "（起点）"},
            {"name": "乙", "role": "同事", "tension": 70, "last_event": "（起点）"},
        ],
        "stress_carryover": 40,
        "career_hold_stages": 0,
        "windows": [],
        "spontaneous_windows": [],
        "_current_stage": 2,
    }


def test_apply_event_effect_clamps_health_and_cash():
    state = _base_state()
    delta = _apply_event_effect(
        state,
        {"effect": {"health": -80, "cash": -10, "debt": 5}, "template": "x"},
    )
    assert state["health_score"] == 0  # 50-80 clamp 到 0
    assert state["finance_ledger"]["cash_months"] == 0
    assert state["finance_ledger"]["debt_months"] == 5
    assert delta["health"] == -80


def test_apply_event_effect_career_hold_and_stress():
    state = _base_state()
    _apply_event_effect(state, {"effect": {"career_hold": 2, "stress": 70}, "template": "x"})
    assert state["career_hold_stages"] == 2
    assert state["stress_carryover"] == 100  # clamp


def test_apply_event_effect_tension_targets_highest():
    state = _base_state()
    delta = _apply_event_effect(state, {"effect": {"tension_top": 15}, "template": "大吵一架"})
    # 张力最高的乙被加压
    by_name = {r["name"]: r for r in state["relationships"]}
    assert by_name["乙"]["tension"] == 85
    assert by_name["甲"]["tension"] == 20  # 甲不动
    assert delta["tension"]["with"] == "乙"


def test_apply_event_effect_opportunity_registers_window():
    state = _base_state()
    _apply_event_effect(state, {"effect": {"opportunity": "referral"}, "template": "x"})
    assert len(state["spontaneous_windows"]) == 1
    win = state["spontaneous_windows"][0]
    assert win["source"] == "luck_event"
    assert win["opens_at_stage"] == 2
    assert win["closes_at_stage"] == 3


# ---------- check_causal_violations ----------

def _ws(career="", family="", resources="", psyche=""):
    return {"career": career, "family": family, "resources": resources, "psyche": psyche}


def test_violation_cash_drop_after_unemployment():
    violations = check_causal_violations(
        prev_realism={},
        prev_world_state=_ws(career="上阶段裸辞，没有收入"),
        new_world_state=_ws(resources="存款充裕，经济明显改善"),
    )
    assert any("存款" in v for v in violations)


def test_violation_career_improve_when_sick():
    violations = check_causal_violations(
        prev_realism={"health_score": 30, "career_hold_stages": 0},
        prev_world_state=_ws(),
        new_world_state=_ws(career="顺利晋升为总监"),
    )
    assert any("晋升" in v for v in violations)


def test_violation_family_harmony_under_tension():
    violations = check_causal_violations(
        prev_realism={"relationships": [{"name": "x", "tension": 90}]},
        prev_world_state=_ws(),
        new_world_state=_ws(family="家庭和睦，其乐融融"),
    )
    assert any("family" in v for v in violations)


def test_violation_psyche_jumpback():
    violations = check_causal_violations(
        prev_realism={"stress_carryover": 80},
        prev_world_state=_ws(psyche="精神崩溃，无法入睡"),
        new_world_state=_ws(psyche="彻底释怀，达到自我接纳"),
    )
    assert any("psyche" in v for v in violations)


def test_no_violation_on_consistent_transition():
    violations = check_causal_violations(
        prev_realism={"health_score": 80, "stress_carryover": 30, "relationships": []},
        prev_world_state=_ws(career="在职", resources="收支平衡"),
        new_world_state=_ws(career="平稳推进", resources="略有结余", psyche="略有起伏"),
    )
    assert violations == []


# ---------- prepare_stage_realism ----------

def test_prepare_stage_realism_decrements_career_hold(monkeypatch):
    # _pick_event 以小时为随机种子，事件效果会改写 career_hold_stages——
    # 锁定无事件，保证断言只验证计数器衰减本身（否则测试随时段漂移）
    monkeypatch.setattr("app.services.realism_layer._pick_event", lambda **kw: None)
    state = _base_state()
    state["career_hold_stages"] = 2
    block, _ = prepare_stage_realism(state, "sess", 3)
    assert state["_current_stage"] == 3
    assert state["career_hold_stages"] == 1
    assert "真实性约束层" in block
    assert "唯一事实来源" in block


def test_prepare_stage_realism_lists_relationships_and_windows():
    state = _base_state()
    state["windows"] = [{
        "window_id": "win_0", "name": "考公上岸", "opens_at_stage": 1,
        "closes_at_stage": 2, "taken": False, "source": "stage_focus",
    }]
    block, _ = prepare_stage_realism(state, "sess", 2)
    assert "甲（朋友）" in block
    assert "考公上岸" in block
