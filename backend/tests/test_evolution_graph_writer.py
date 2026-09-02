"""推演独立图谱（方案 a：与主图谱物理隔离）单元测试"""
import threading
from unittest.mock import MagicMock, patch

import pytest

from app.models.project import Project, ProjectStatus
from app.services import evolution_graph_writer as egw


def _make_project(**kw):
    return Project(
        project_id=kw.get("project_id", "proj_test"),
        name=kw.get("name", "测试项目"),
        status=ProjectStatus.GRAPH_COMPLETED,
        created_at="2026-01-01 00:00:00",
        updated_at="2026-01-01 00:00:00",
        graph_id=kw.get("graph_id", "prism_main123"),
        evolution_graph_id=kw.get("evolution_graph_id"),
    )


def _make_session_entry():
    session = {
        "session_id": "sess_abc",
        "source_branch_archetype": "aggressive",
        "source_branch_positioning": "揭示真相",
    }
    entry = {
        "stage_index": 1,
        "stage_label": "寄信",
        "occurred_events": ["她把信交给了邻居"],
        "state_snapshot": "平静地等待终点",
        "world_state": {"psyche": "释然"},
    }
    return session, entry


class TestSeparateGraph:
    def test_creates_evolution_graph_lazily(self):
        """无推演图谱时自动创建独立图谱，不碰主图谱"""
        project = _make_project()
        session, entry = _make_session_entry()
        with patch.object(egw, "get_zep_client") as mock_zep, \
                patch.object(egw, "ProjectManager") as mock_pm:
            client = MagicMock()
            mock_zep.return_value = client
            egw.write_stage_to_graph(project, session, entry)

            # 创建了独立图谱（prismevo_ 前缀），且未删除/未写入主图谱
            created_ids = [
                call.kwargs["graph_id"]
                for call in client.graph.create.call_args_list
            ]
            assert len(created_ids) == 1
            assert created_ids[0].startswith("prismevo_")
            assert project.evolution_graph_id == created_ids[0]
            assert project.graph_id == "prism_main123"  # 主图谱未动
            mock_pm.save_project.assert_called_once_with(project)

            # episode 写入的是独立图谱
            add_call = client.graph.add.call_args
            assert add_call.kwargs["graph_id"] == created_ids[0]

    def test_reuses_existing_evolution_graph(self):
        """已有推演图谱时不重复创建"""
        project = _make_project(evolution_graph_id="prismevo_exists")
        session, entry = _make_session_entry()
        with patch.object(egw, "get_zep_client") as mock_zep:
            client = MagicMock()
            mock_zep.return_value = client
            egw.write_stage_to_graph(project, session, entry)
            client.graph.create.assert_not_called()
            assert client.graph.add.call_args.kwargs["graph_id"] == "prismevo_exists"

    def test_write_failure_returns_none(self):
        """写入失败不抛异常（不阻断推演主流程）"""
        project = _make_project(evolution_graph_id="prismevo_x")
        session, entry = _make_session_entry()
        with patch.object(egw, "get_zep_client") as mock_zep:
            client = MagicMock()
            client.graph.add.side_effect = RuntimeError("zep down")
            mock_zep.return_value = client
            assert egw.write_stage_to_graph(project, session, entry) is None

    def test_creation_failure_returns_none(self):
        """图谱创建失败不抛异常"""
        project = _make_project()
        session, entry = _make_session_entry()
        with patch.object(egw, "get_zep_client") as mock_zep:
            mock_zep.side_effect = RuntimeError("no api key")
            assert egw.write_stage_to_graph(project, session, entry) is None

    def test_stage_text_marks_fiction(self):
        """写入文本明确标注虚构推演，且含会话标识"""
        session, entry = _make_session_entry()
        text = egw._build_stage_text(session, entry)
        assert "虚构推演，非真实人生" in text
        assert "sess_abc" in text
        assert "她把信交给了邻居" in text

    def test_concurrent_creation_single_graph(self):
        """并发首次写入只创建一个图谱（懒创建锁）"""
        project = _make_project()
        session, entry = _make_session_entry()
        created = []
        created_lock = threading.Lock()

        with patch.object(egw, "get_zep_client") as mock_zep, \
                patch.object(egw, "ProjectManager"):
            client = MagicMock()

            def slow_create(**kwargs):
                import time
                time.sleep(0.05)
                with created_lock:
                    created.append(kwargs["graph_id"])
                return MagicMock()

            client.graph.create.side_effect = slow_create
            mock_zep.return_value = client

            threads = [
                threading.Thread(
                    target=egw.write_stage_to_graph, args=(project, session, entry)
                )
                for _ in range(4)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(created) == 1
            # 每个线程的 episode 都写进同一个图谱
            written = {
                call.kwargs["graph_id"] for call in client.graph.add.call_args_list
            }
            assert written == set(created)


class TestDeleteEvolutionGraph:
    def test_delete_clears_reference(self):
        project = _make_project(evolution_graph_id="prismevo_del")
        with patch.object(egw, "get_zep_client") as mock_zep:
            client = MagicMock()
            mock_zep.return_value = client
            egw.delete_evolution_graph(project)
            client.graph.delete.assert_called_once_with(graph_id="prismevo_del")
            assert project.evolution_graph_id is None

    def test_delete_failure_still_clears_reference(self):
        """删除失败也清除引用（不留死引用）"""
        project = _make_project(evolution_graph_id="prismevo_stuck")
        with patch.object(egw, "get_zep_client") as mock_zep:
            client = MagicMock()
            client.graph.delete.side_effect = RuntimeError("404")
            mock_zep.return_value = client
            egw.delete_evolution_graph(project)
            assert project.evolution_graph_id is None

    def test_noop_when_absent(self):
        project = _make_project(evolution_graph_id=None)
        with patch.object(egw, "get_zep_client") as mock_zep:
            egw.delete_evolution_graph(project)
            mock_zep.assert_not_called()
