"""EvolutionEngine 单元测试：mock _chat_json_with_retry，不发起真实 LLM 调用。"""

import pytest

from app.services import evolution_engine
from app.services.evolution_engine import EvolutionEngine


@pytest.fixture
def engine():
    return EvolutionEngine(api_key="test-key")


@pytest.fixture
def personal_model():
    return {
        "model_version": "v1",
        "basic_info": {"age": 35, "gender": "男", "location": "杭州"},
        "personality": ["谨慎"],
        "aspirations": "做自己的产品",
        "current_state": "在公司任职，现金流够撑9个月",
        "conflicts": [],
        "emotional_patterns": [],
        "relationships": [
            {"person": "宋婉", "relation": "妻子", "closeness": "close", "influence": "支持"},
        ],
    }


@pytest.fixture
def branch():
    return {
        "archetype": "builder",
        "positioning": "独立开发者路线",
        "timeline": [{"year": "2026", "event": "启动副业"}],
        "key_assumption": "有 12 个月生活费储备",
    }


def _llm_result(**payload):
    """构造 _chat_json_with_retry 的返回值。"""
    base = {
        "stage_plan": [
            {"stage_label": f"阶段{i}", "focus": f"焦点{i}"} for i in range(1, 7)
        ],
        "forks": [
            {"at_stage": 1, "question": "是否辞职", "options": [
                {"label": "辞"}, {"label": "不辞"}]},
            # options 不足 2 个 → 应被丢弃
            {"at_stage": 2, "question": "坏分叉", "options": [{"label": "唯一"}]},
            # at_stage 越界 → 应被钳制
            {"at_stage": 99, "question": "远期分叉", "options": [
                {"label": "A"}, {"label": "B"}]},
        ],
    }
    base.update(payload)
    return base


# ---------- create_session ----------

def test_create_session_shapes_and_clamps(engine, personal_model, branch, monkeypatch):
    calls = []

    def fake_chat(llm, *, messages, max_tokens):
        calls.append(messages)
        return _llm_result()

    monkeypatch.setattr(evolution_engine, "_chat_json_with_retry", fake_chat)

    session = engine.create_session("proj-1", branch, personal_model, stage_count=4)

    # stage_plan 裁剪到 stage_count
    assert len(session["stage_plan"]) == 4
    # 无效分叉被丢弃、at_stage 被钳制到计划长度内
    assert len(session["pending_forks"]) == 2
    assert session["pending_forks"][0]["at_stage"] == 1
    assert session["pending_forks"][1]["at_stage"] == 4
    assert session["pending_forks"][0]["resolved"] is None
    # 基本字段
    assert session["session_id"].startswith("evo_")
    assert session["status"] == "active"
    assert session["source_branch_archetype"] == "builder"
    assert session["source_model_version"] == "v1"
    # realism 账本已初始化：现金流解析 + 画像关系人
    assert session["realism_state"]["finance_ledger"]["cash_months"] == 9
    names = [r["name"] for r in session["realism_state"]["relationships"]]
    assert "宋婉" in names


def test_create_session_requires_stage_plan(engine, personal_model, branch, monkeypatch):
    monkeypatch.setattr(
        evolution_engine, "_chat_json_with_retry",
        lambda llm, *, messages, max_tokens: {"stage_plan": [], "forks": []},
    )
    with pytest.raises(ValueError, match="stage_plan"):
        engine.create_session("proj-1", branch, personal_model)


# ---------- advance ----------

def _make_session(personal_model, plan=None):
    from app.services.realism_layer import init_realism_state

    plan = plan or [
        {"stage_label": "阶段1", "focus": "试水"},
        {"stage_label": "阶段2", "focus": "扩张"},
    ]
    return {
        "session_id": "evo_test",
        "project_id": "p1",
        "source_branch_positioning": "独立开发者",
        "source_branch_timeline": [],
        "stage_plan": plan,
        "stage_history": [],
        "pending_forks": [],
        "user_events": [],
        "status": "active",
        "initial_state": "推演起点",
        "realism_state": init_realism_state(personal_model, [], plan),
    }


def _advance_payload(**overrides):
    payload = {
        "world_state": {"career": "稳步推进", "family": "平稳",
                        "resources": "收支平衡", "psyche": "略有焦虑"},
        "occurred_events": ["完成第一个版本"],
        "state_snapshot": "三个月里完成了 MVP 并拿到首批用户。",
        "divergence_note": None,
        "realism_delta": {
            "health_delta": -5,
            "cash_delta": -1,
            "debt_delta": 0,
            "stress_delta": 10,
        },
    }
    payload.update(overrides)
    return payload


def test_advance_appends_history_and_merges_ledger(engine, personal_model, monkeypatch):
    monkeypatch.setattr(
        evolution_engine, "_chat_json_with_retry",
        lambda llm, *, messages, max_tokens: _advance_payload(),
    )
    # 锁定意外事件抽取结果为 None（时间种子导致测试在不同时段抽取不同事件）
    from app.services import realism_layer
    monkeypatch.setattr(realism_layer, "_pick_event", lambda **kwargs: None)
    session = _make_session(personal_model)
    before = {
        "health": session["realism_state"]["health_score"],
        "cash": session["realism_state"]["finance_ledger"]["cash_months"],
        "stress": session["realism_state"]["stress_carryover"],
    }

    result = engine.advance(session)

    assert result["fork_required"] is False
    entry = session["stage_history"][0]
    assert entry["stage_index"] == 1
    assert entry["stage_label"] == "阶段1"
    assert entry["world_state"]["career"] == "稳步推进"
    assert entry["occurred_events"] == ["完成第一个版本"]
    # 账本按 delta 合并
    rs = session["realism_state"]
    assert rs["health_score"] == before["health"] - 5
    assert rs["finance_ledger"]["cash_months"] == max(0, before["cash"] - 1)
    assert rs["stress_carryover"] == min(100, before["stress"] + 10)
    # 快照随 entry 落盘
    assert entry["realism"]["finance"]["cash_months"] == rs["finance_ledger"]["cash_months"]
    assert session["status"] == "active"  # 还剩阶段2


def test_advance_prompt_uses_third_person_and_initial_state(engine, personal_model, monkeypatch):
    """叙事人称规则 + 主角称呼注入；首阶段起点状态（initial_state 键名修复）进入 prompt"""
    captured = {}

    def fake_chat(llm, *, messages, max_tokens):
        captured["prompt"] = messages[1]["content"]
        return _advance_payload()

    monkeypatch.setattr(evolution_engine, "_chat_json_with_retry", fake_chat)
    from app.services import realism_layer
    monkeypatch.setattr(realism_layer, "_pick_event", lambda **kwargs: None)

    session = _make_session(personal_model)
    session["protagonist"] = "阿禾"
    engine.advance(session)

    prompt = captured["prompt"]
    assert "叙事人称" in prompt
    assert "「阿禾」" in prompt
    assert "推演起点" in prompt  # 修复前读错键名，首阶段起点为空


def test_create_session_stores_protagonist(engine, personal_model, monkeypatch):
    """create_session 从画像昵称提取叙事主角称呼，无昵称回落「主角」"""
    monkeypatch.setattr(
        evolution_engine, "_chat_json_with_retry",
        lambda llm, *, messages, max_tokens: {
            "stage_plan": [{"stage_label": "阶段1", "focus": "起步"}],
            "forks": [],
        },
    )
    branch = {"archetype": "A", "positioning": "", "timeline": [], "key_assumption": ""}
    session = engine.create_session("p1", branch, personal_model)
    assert session["protagonist"] == "主角"  # 夹具无昵称

    personal_model["basic_info"]["nickname"] = "林一"
    session2 = engine.create_session("p1", branch, personal_model)
    assert session2["protagonist"] == "林一"


def test_advance_completes_session_on_last_stage(engine, personal_model, monkeypatch):
    monkeypatch.setattr(
        evolution_engine, "_chat_json_with_retry",
        lambda llm, *, messages, max_tokens: _advance_payload(),
    )
    session = _make_session(personal_model, plan=[{"stage_label": "终局", "focus": "收官"}])
    engine.advance(session)
    assert session["status"] == "completed"
    with pytest.raises(ValueError, match="无法推进"):
        engine.advance(session)


def test_advance_blocked_by_pending_fork(engine, personal_model, monkeypatch):
    def fail(llm, **kwargs):
        raise AssertionError("分叉未决时不应调用 LLM")

    monkeypatch.setattr(evolution_engine, "_chat_json_with_retry", fail)
    session = _make_session(personal_model)
    session["pending_forks"] = [{
        "fork_id": "fork_1", "at_stage": 1, "question": "是否辞职",
        "options": [{"label": "辞"}, {"label": "不辞"}], "resolved": None,
    }]

    result = engine.advance(session)

    assert result["fork_required"] is True
    assert result["fork"]["fork_id"] == "fork_1"
    assert session["stage_history"] == []  # 未推进


def test_advance_retries_on_causal_violation(engine, personal_model, monkeypatch):
    """第一版 world_state 违反因果（病中晋升），应触发第二次 LLM 调用。"""
    responses = [
        _advance_payload(world_state={"career": "火速晋升总监", "family": "平",
                                      "resources": "平", "psyche": "平"}),
        _advance_payload(world_state={"career": "带病维持现状", "family": "平",
                                      "resources": "平", "psyche": "平"}),
    ]
    calls = []

    def fake_chat(llm, *, messages, max_tokens):
        calls.append(messages)
        return responses[len(calls) - 1]

    monkeypatch.setattr(evolution_engine, "_chat_json_with_retry", fake_chat)

    session = _make_session(personal_model)
    session["realism_state"]["career_hold_stages"] = 1  # 处于职业受限期
    session["realism_state"]["health_score"] = 60

    engine.advance(session)

    assert len(calls) == 2  # 违规触发重试
    # 第二次调用的 system prompt 携带修正提示
    assert "修正提示" in calls[1][0]["content"]
    # 最终采纳修正后的版本
    assert session["stage_history"][0]["world_state"]["career"] == "带病维持现状"


def test_advance_inactive_session_raises(engine, personal_model):
    session = _make_session(personal_model)
    session["status"] = "completed"
    with pytest.raises(ValueError, match="无法推进"):
        engine.advance(session)


def test_advance_records_window_taken(engine, personal_model, monkeypatch):
    monkeypatch.setattr(
        evolution_engine, "_chat_json_with_retry",
        lambda llm, *, messages, max_tokens: _advance_payload(
            realism_delta={"window_takens": ["考公上岸"]},
        ),
    )
    session = _make_session(personal_model)
    session["realism_state"]["windows"] = [{
        "window_id": "win_0", "name": "考公上岸", "opens_at_stage": 1,
        "closes_at_stage": 2, "taken": False, "source": "stage_focus",
    }]
    engine.advance(session)
    assert session["realism_state"]["windows"][0]["taken"] is True


# ---------- prepare_initial_state ----------

def test_prepare_initial_state_appends_basic_info(personal_model):
    session = {}
    EvolutionEngine.prepare_initial_state(session, personal_model)
    text = session["initial_state"]
    assert "推演起点" not in text  # current_state 为正文
    assert "现金流够撑9个月" in text
    assert "年龄: 35" in text
    assert "性别: 男" in text


def test_prepare_initial_state_skips_empty_fields():
    session = {}
    model = {"current_state": "起点", "basic_info": {"age": None, "gender": "", "location": "上海"}}
    EvolutionEngine.prepare_initial_state(session, model)
    text = session["initial_state"]
    assert "年龄" not in text
    assert "性别" not in text
    assert "所在城市: 上海" in text
