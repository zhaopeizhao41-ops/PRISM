import uuid

from app.services.profile_materials import canonicalize_goals, free_material_to_text, build_evidence_index
from app.services.profile_synthesizer import _backfill_evidence_refs
from app.models.task import TaskManager, TaskStatus
from app.services.realism_layer import init_realism_state, check_circuit_breakers
from app.services.evolution_engine import EvolutionEngine


def test_fictional_material_is_explicit_and_indexed():
    block = free_material_to_text("Gregor woke up changed.", "literary", material_mode="fictional")
    assert "模式: fictional" in block
    index = build_evidence_index("mat_x", block)
    assert index and index[0]["chunk_id"] == "mat_x:c0"


def test_goal_polarity_preserved_and_legacy_adapted():
    goals = canonicalize_goals({
        "goal_short_term": "完成作品",
        "want_to_avoid": "不要被工作定义",
    })
    assert [(g["content"], g["polarity"]) for g in goals] == [
        ("完成作品", "want"),
        ("不要被工作定义", "want_to_avoid"),
    ]


def test_pressure_debt_does_not_immediately_mean_insolvency():
    state = init_realism_state(
        {"basic_info": {"financial_state": "压力大有负债"}}, [], []
    )
    ledger = state["finance_ledger"]
    assert ledger["cash_months"] == 1
    assert ledger["debt_months"] == 1
    assert check_circuit_breakers(state, 1, []) is None


def test_breaker_episode_dedupes_across_stages_and_effects_apply():
    state = {
        "finance_ledger": {"cash_months": 0, "debt_months": 2, "known": True},
        "health_score": 80,
        "relationships": [],
        "breaker_episodes": {},
    }
    first = check_circuit_breakers(state, 1, [])
    assert first and first["breaker_key"] == "insolvency"
    second = check_circuit_breakers(state, 2, [first])
    assert second is None
    session = {"session_id": "evo_test", "pending_forks": [first], "realism_state": state}
    EvolutionEngine().resolve_fork(session, first["fork_id"], 0)
    assert state["finance_ledger"]["cash_months"] == 1
    assert state["finance_ledger"]["debt_months"] == 1
    assert state["breaker_episodes"]["insolvency"]["status"] == "acknowledged"


def test_acknowledged_episode_recovers_then_can_reopen():
    state = {
        "finance_ledger": {"cash_months": 1, "debt_months": 1, "known": True},
        "health_score": 80,
        "relationships": [],
        "breaker_episodes": {
            "insolvency": {"episode_id": "br_old", "status": "acknowledged"}
        },
    }
    assert check_circuit_breakers(state, 2, []) is None
    assert state["breaker_episodes"]["insolvency"]["status"] == "recovered"
    state["finance_ledger"].update(cash_months=0, debt_months=2)
    fork = check_circuit_breakers(state, 3, [])
    assert fork and fork["breaker_key"] == "insolvency"


def test_model_evidence_refs_are_backfilled_only_from_verified_quotes():
    manifest = [{
        "material_id": "mat_diary",
        "material_type": "diary",
        "chunks": build_evidence_index("mat_diary", "今天我决定辞职，去学习新的技能。"),
    }]
    model = {"milestones": [{
        "summary": "决定辞职",
        "source": "diary",
        "evidence": "今天我决定辞职",
    }]}
    warnings = _backfill_evidence_refs(model, manifest)
    ref = model["milestones"][0]["evidence_refs"][0]
    assert not warnings
    assert ref["material_id"] == "mat_diary"
    assert ref["chunk_id"] == "mat_diary:c0"
    assert ref["quote"] == "今天我决定辞职"


def test_cancelled_task_is_terminal_and_cannot_be_resurrected():
    manager = TaskManager()
    task_id = manager.create_task("contract-test")
    task = manager.cancel_task(task_id, "test cancellation")
    assert task and task.status == TaskStatus.CANCELLED
    assert manager.is_cancelled(task_id)
    assert manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=10) is False
    assert manager.get_task(task_id).status == TaskStatus.CANCELLED


def test_task_listing_filters_by_project_metadata():
    manager = TaskManager()
    project_id = f"task-filter-{uuid.uuid4().hex}"
    own_task = manager.create_task(
        "自己的任务",
        metadata={"project_id": project_id, "kind": "profile_model"},
    )
    other_task = manager.create_task(
        "其他项目任务",
        metadata={"project_id": f"other-{uuid.uuid4().hex}", "kind": "branch_generation"},
    )

    try:
        listed = manager.list_tasks(project_id=project_id)
        assert [task["task_id"] for task in listed] == [own_task]
        assert listed[0]["metadata"]["kind"] == "profile_model"
    finally:
        with manager._task_lock:
            manager._tasks.pop(own_task, None)
            manager._tasks.pop(other_task, None)
            manager._cancel_events.pop(own_task, None)
            manager._cancel_events.pop(other_task, None)
            manager._persist_locked()
