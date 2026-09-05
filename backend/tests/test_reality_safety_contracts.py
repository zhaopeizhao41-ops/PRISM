import threading
import time
import uuid

from flask import Flask

from app.services.profile_materials import canonicalize_goals, free_material_to_text, build_evidence_index
from app.services.profile_synthesizer import _backfill_evidence_refs
from app.models.task import TaskManager, TaskStatus
from app.services.realism_layer import init_realism_state, check_circuit_breakers
from app.services.evolution_engine import EvolutionEngine
from app.api.evolution import _comparison_realism
from app.api import roundtable as roundtable_api


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


def test_paused_task_waits_until_resumed_and_cancel_wakes_worker():
    manager = TaskManager()
    task_id = manager.create_task("pause-contract")
    try:
        manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=42)
        paused = manager.pause_task(task_id)
        assert paused and paused.status == TaskStatus.PAUSED
        assert manager.get_task(task_id).to_dict()["status"] == "paused"

        started = threading.Event()
        finished = threading.Event()
        result = []

        def worker():
            started.set()
            result.append(manager.wait_if_paused(task_id, wait_seconds=0.01))
            finished.set()

        thread = threading.Thread(target=worker)
        thread.start()
        assert started.wait(1)
        time.sleep(0.03)
        assert not finished.is_set()

        manager.resume_task(task_id)
        assert finished.wait(1)
        assert result == [True]
        thread.join(timeout=1)
    finally:
        with manager._task_lock:
            manager._tasks.pop(task_id, None)
            manager._cancel_events.pop(task_id, None)
            manager._resume_events.pop(task_id, None)
            manager._persist_locked()


def test_cancel_wakes_paused_task_waiter():
    manager = TaskManager()
    task_id = manager.create_task("pause-cancel-contract")
    try:
        manager.update_task(task_id, status=TaskStatus.PROCESSING)
        manager.pause_task(task_id)
        finished = threading.Event()
        result = []

        def worker():
            result.append(manager.wait_if_paused(task_id, wait_seconds=0.01))
            finished.set()

        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.03)
        manager.cancel_task(task_id)
        assert finished.wait(1)
        assert result == [False]
        thread.join(timeout=1)
    finally:
        with manager._task_lock:
            manager._tasks.pop(task_id, None)
            manager._cancel_events.pop(task_id, None)
            manager._resume_events.pop(task_id, None)
            manager._persist_locked()


def test_roundtable_pause_resume_endpoints_return_updated_task(monkeypatch):
    app = Flask(__name__)
    dialog = {
        "dialog_id": "rt_contract",
        "project_id": "project_contract",
        "task_id": "task_contract",
        "status": "running",
    }

    class FakeTask:
        def __init__(self):
            self.status = TaskStatus.PROCESSING
            self.metadata = {"kind": "roundtable"}

        def to_dict(self):
            return {"task_id": "task_contract", "status": self.status.value}

    class FakeManager:
        def __init__(self):
            self.task = FakeTask()

        def get_task(self, task_id):
            return self.task if task_id == "task_contract" else None

        def pause_task(self, task_id, reason):
            self.task.status = TaskStatus.PAUSED
            return self.task

        def resume_task(self, task_id, reason):
            self.task.status = TaskStatus.PROCESSING
            return self.task

    manager = FakeManager()
    saved = []
    monkeypatch.setattr(roundtable_api, "TaskManager", lambda: manager)
    monkeypatch.setattr(roundtable_api.RoundtableStore, "get", staticmethod(lambda project_id, dialog_id: dialog))
    monkeypatch.setattr(roundtable_api.RoundtableStore, "save", staticmethod(lambda value: saved.append(value.copy())))

    with app.test_request_context("/api/roundtable/rt_contract/pause", method="POST", json={"project_id": "project_contract"}):
        paused_response = roundtable_api.pause_dialog("rt_contract")
    paused = paused_response.get_json()
    assert paused["success"] is True
    assert paused["data"]["task"]["status"] == "paused"
    assert dialog["status"] == "paused"

    with app.test_request_context("/api/roundtable/rt_contract/resume", method="POST", json={"project_id": "project_contract"}):
        resumed_response = roundtable_api.resume_dialog("rt_contract")
    resumed = resumed_response.get_json()
    assert resumed["success"] is True
    assert resumed["data"]["task"]["status"] == "processing"
    assert dialog["status"] == "running"
    assert len(saved) == 2


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
            manager._resume_events.pop(own_task, None)
            manager._resume_events.pop(other_task, None)
            manager._persist_locked()


def test_task_public_contract_redacts_tracebacks_and_classifies_errors():
    manager = TaskManager()
    task_id = manager.create_task(
        "模型任务",
        metadata={"project_id": f"task-contract-{uuid.uuid4().hex}", "kind": "profile_model"},
    )
    try:
        updated = manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="画像合成失败: provider request failed",
            error=(
                "Traceback (most recent call last):\n"
                "  File '/srv/prism/app.py', line 12, in run\n"
                "ValueError: provider request failed with sk-test-secret-key"
            ),
        )
        assert updated is True
        payload = manager.get_task(task_id).to_dict()
        assert "Traceback" not in payload["error"]
        assert "/srv/prism" not in payload["error"]
        assert "sk-test-secret-key" not in payload["error"]
        assert payload["error_code"] == "task_failed"
        assert payload["retryable"] is True
    finally:
        with manager._task_lock:
            manager._tasks.pop(task_id, None)
            manager._cancel_events.pop(task_id, None)
            manager._persist_locked()


def test_task_configuration_failure_is_not_marked_retryable():
    manager = TaskManager()
    task_id = manager.create_task("画像任务")
    try:
        manager.fail_task(task_id, "ValueError: LLM_API_KEY 未配置")
        payload = manager.get_task(task_id).to_dict()
        assert payload["error_code"] == "configuration_error"
        assert payload["retryable"] is False
        assert payload["error"] == "ValueError: LLM_API_KEY 未配置"
    finally:
        with manager._task_lock:
            manager._tasks.pop(task_id, None)
            manager._cancel_events.pop(task_id, None)
            manager._persist_locked()


def test_comparison_realism_summary_preserves_known_values_and_omits_invalid_values():
    summary = _comparison_realism({
        "health_score": 72,
        "stress_carryover": "not-a-number",
        "finance": {
            "cash_months": 3,
            "debt_months": True,
            "income_stability": 4,
            "known": True,
        },
        "relationships": [
            {"name": "母亲", "role": "family", "tension": 64, "last_event": "争执"},
            "malformed",
        ],
        "life_event": {"id": "evt_1", "kind": "illness", "template": ""},
        "causal_violations": ["constraint one", ""],
    })
    assert summary["health_score"] == 72
    assert summary["stress_carryover"] is None
    assert summary["finance"] == {
        "cash_months": 3,
        "debt_months": None,
        "income_stability": 4,
        "known": True,
    }
    assert summary["relationships"] == [{
        "name": "母亲",
        "role": "family",
        "tension": 64,
        "last_event": "争执",
    }]
    assert summary["life_event"]["kind"] == "illness"
    assert summary["causal_violations"] == ["constraint one"]
