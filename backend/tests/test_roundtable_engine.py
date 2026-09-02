"""RoundtableEngine 单元测试：mock Store 与 LLM，不落盘、不发起真实调用。"""

import pytest

from app.services import roundtable_engine as rt
from app.services.roundtable_engine import RoundtableEngine


def _session(sid, archetype, positioning, depth):
    return {
        "session_id": sid,
        "source_branch_archetype": archetype,
        "source_branch_positioning": positioning,
        "stage_count": depth + 1,
        "status": "active",
        "stage_history": [
            {"stage_label": f"阶段{i}", "state_snapshot": f"{archetype}第{i}阶段",
             "world_state": {"career": "推进", "family": "平稳"},
             "divergence_note": None}
            for i in range(1, depth + 1)
        ],
        "stage_plan": [{"stage_label": f"阶段{i}"} for i in range(1, depth + 2)],
    }


@pytest.fixture
def sessions():
    return {
        "s_deep": _session("s_deep", "builder", "独立开发", 3),
        "s_shallow": _session("s_shallow", "scholar", "学术深造", 1),
    }


@pytest.fixture
def card():
    return {
        "person_ref": "老陈",
        "relation_kind": "前合伙人",
        "persona": "务实的生意人",
        "core_concern": "投资回报",
        "communication_style": "直接",
        "known_positions": [{"topic": "辞职", "stance": "反对", "evidence": "风险太大"}],
        "blind_spots": ["低估情感因素"],
        "resistance_clause": "不会被宏大愿景说服",
        "thin": False,
    }


class _FakeEvolutionStore:
    def __init__(self, sessions):
        self._sessions = sessions

    def list_sessions(self, project_id):
        # list_participants 读取摘要字段
        return [
            {"session_id": sid, "stages_done": len(s["stage_history"]),
             "status": s["status"], "source_branch_archetype": s["source_branch_archetype"],
             "source_branch_positioning": s["source_branch_positioning"],
             "stage_count": s["stage_count"]}
            for sid, s in self._sessions.items()
        ]

    def get(self, project_id, session_id):
        return self._sessions[session_id]


class _FakeRelationshipAgentStore:
    _cards = []

    @staticmethod
    def get_current(project_id):
        return {"cards": _FakeRelationshipAgentStore._cards}

    @staticmethod
    def get_corrections(project_id):
        return {}


def _install_stores(monkeypatch, sessions, cards):
    fake_evo = _FakeEvolutionStore(sessions)
    _FakeRelationshipAgentStore._cards = cards
    monkeypatch.setattr(rt, "EvolutionStore", fake_evo)
    monkeypatch.setattr(rt, "RelationshipAgentStore", _FakeRelationshipAgentStore)


def test_universe_label():
    assert RoundtableEngine._universe_label({"source_branch_archetype": "builder"}) == "builder宇宙的我"


def test_list_participants_sorts_by_depth(monkeypatch, sessions, card):
    engine = RoundtableEngine(api_key="test-key")
    _install_stores(monkeypatch, sessions, [card])

    result = engine.list_participants("p1")

    # 宇宙按推演深度升序（浅→深）
    assert [u["session_id"] for u in result["universes"]] == ["s_shallow", "s_deep"]
    assert result["universes"][0]["label"] == "scholar宇宙的我"
    # 关系人摘要
    assert result["related"] == [{
        "person_ref": "老陈", "relation_kind": "前合伙人", "thin": False,
        "persona": "务实的生意人",
    }]


def test_run_roundtable_order_and_moderation(monkeypatch, sessions, card):
    engine = RoundtableEngine(api_key="test-key")
    _install_stores(monkeypatch, sessions, [card])

    llm_outputs = [
        "浅宇宙先发言：先观望。",
        "深宇宙后发言：已经跑通了。",
        "老陈说：我反对。",   # 关系人
        {"verdicts": [], "summary": "审计结论", "advice": "建议"},  # 主持人
    ]
    calls = []

    def fake_chat(llm, *, messages, max_tokens, expect_json=False):
        calls.append({"max_tokens": max_tokens, "expect_json": expect_json})
        out = llm_outputs[len(calls) - 1]
        return out

    monkeypatch.setattr(rt, "_chat_with_retry", fake_chat)

    dialog = {
        "topic": "该不该辞职",
        "project_id": "p1",
        "participants": [
            {"type": "universe", "session_id": "s_shallow"},
            {"type": "universe", "session_id": "s_deep"},
            {"type": "related", "person_ref": "老陈", "_card": card},
        ],
    }
    speeches_seen = []
    result = engine.run_roundtable(
        dialog,
        personal_model={"basic_info": {}, "personality": [], "current_state": ""},
        progress_callback=lambda stage, payload: speeches_seen.append(stage),
    )

    # 发言顺序：宇宙（按 participants 顺序）→ 关系人 → 主持人审计
    transcript = result["transcript"]
    assert [s["speaker"] for s in transcript] == [
        "scholar宇宙的我", "builder宇宙的我", "老陈",
    ]
    assert [s["speaker_type"] for s in transcript] == ["universe", "universe", "related"]
    assert transcript[0]["ref"] == "s_shallow"
    assert "观望" in transcript[0]["content"]
    # 最后一次 LLM 调用是主持人（expect_json=True）
    assert calls[-1]["expect_json"] is True


def test_run_roundtable_multi_rounds(monkeypatch, sessions, card):
    engine = RoundtableEngine(api_key="test-key")
    _install_stores(monkeypatch, sessions, [card])

    # 2 轮圆桌：每轮 2 个宇宙 + 1 个关系人 = 3 条发言，共 6 条发言 + 1 次主持人审计 = 7 次调用
    llm_outputs = [
        # 第 1 轮
        {"speech": "第1轮：学者立论", "core_memory_edits": [{"block": "human", "action": "append", "content": "初次判断"}]},
        {"speech": "第1轮：独立开发者立论", "core_memory_edits": []},
        {"speech": "第1轮：老陈表态反对", "core_memory_edits": []},
        # 第 2 轮
        {"speech": "第2轮：学者质疑商业风险", "core_memory_edits": []},
        {"speech": "第2轮：独立开发者反驳老陈", "core_memory_edits": [{"block": "situation", "action": "replace", "target": "局势", "content": "全面抗辩"}]},
        {"speech": "第2轮：老陈施压现实账目", "core_memory_edits": []},
        # 主持人跨轮审计
        {"summary": "多轮深度辩论审计结论", "convergences": [], "divergences": []},
    ]
    calls = []

    def fake_chat(llm, *, messages, max_tokens, expect_json=False):
        calls.append({"messages": messages, "max_tokens": max_tokens, "expect_json": expect_json})
        return llm_outputs[len(calls) - 1]

    monkeypatch.setattr(rt, "_chat_with_retry", fake_chat)

    dialog = {
        "topic": "该不该辞职",
        "project_id": "p1",
        "total_rounds": 2,
        "participants": [
            {"type": "universe", "session_id": "s_shallow"},
            {"type": "universe", "session_id": "s_deep"},
            {"type": "related", "person_ref": "老陈", "_card": card},
        ],
    }
    speeches_seen = []
    result = engine.run_roundtable(
        dialog,
        personal_model={"basic_info": {}, "personality": [], "current_state": ""},
        progress_callback=lambda stage, payload: speeches_seen.append(stage),
    )

    assert dialog["total_rounds"] == 2
    transcript = result["transcript"]
    assert len(transcript) == 6
    assert [s["round"] for s in transcript] == [1, 1, 1, 2, 2, 2]
    assert transcript[0]["content"] == "第1轮：学者立论"
    assert transcript[3]["content"] == "第2轮：学者质疑商业风险"
    assert "全面抗辩" in transcript[4]["core_memory"]["situation"]
    assert speeches_seen.count("speech") == 6
    assert "moderate" in speeches_seen

