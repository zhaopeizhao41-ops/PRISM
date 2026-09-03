import pytest

from app import create_app
from app.api import graph as graph_api
from app.models.project import ProjectManager, ProjectStatus
from app.utils.zep_lifecycle import register_graph_reader, unregister_graph_reader


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    item = ProjectManager.create_project('图谱清理测试')
    item.project_type = 'personal_profile'
    item.status = ProjectStatus.GRAPH_COMPLETED
    item.graph_id = 'graph-personal'
    item.literary_graph_id = 'graph-literary'
    item.ontology = {'entity_types': [], 'edge_types': []}
    ProjectManager.save_project(item)
    return item


@pytest.fixture
def client(project):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_profile_delete_removes_personal_and_literary_graphs(
    client, project, monkeypatch
):
    deleted = []
    monkeypatch.setattr(
        graph_api,
        '_delete_cloud_graph_if_present',
        lambda graph_id: deleted.append(graph_id),
    )
    monkeypatch.setattr(graph_api, '_delete_project_evolution_graph', lambda _project: None)

    response = client.delete(f'/api/profile/project/{project.project_id}')

    assert response.status_code == 200
    assert deleted == ['graph-literary', 'graph-personal']
    assert ProjectManager.get_project(project.project_id) is None


def test_reset_clears_both_cloud_graph_references(client, project, monkeypatch):
    deleted = []
    monkeypatch.setattr(
        graph_api,
        '_delete_cloud_graph_if_present',
        lambda graph_id: deleted.append(graph_id),
    )
    monkeypatch.setattr(graph_api, '_delete_project_evolution_graph', lambda _project: None)

    response = client.post(f'/api/graph/project/{project.project_id}/reset')

    assert response.status_code == 200
    assert deleted == ['graph-literary', 'graph-personal']
    reset = ProjectManager.get_project(project.project_id)
    assert reset.graph_id is None
    assert reset.literary_graph_id is None
    assert reset.status == ProjectStatus.ONTOLOGY_GENERATED


def test_busy_literary_graph_blocks_delete_before_any_graph_is_removed(
    client, project, monkeypatch
):
    deleted = []
    monkeypatch.setattr(
        graph_api,
        '_delete_cloud_graph_if_present',
        lambda graph_id: deleted.append(graph_id),
    )
    register_graph_reader('graph-literary', 'report:test')
    try:
        response = client.delete(f'/api/profile/project/{project.project_id}')
    finally:
        unregister_graph_reader('graph-literary', 'report:test')

    assert response.status_code == 409
    assert deleted == []
    assert ProjectManager.get_project(project.project_id) is not None


def test_delete_graph_endpoint_clears_only_the_selected_reference(
    client, project, monkeypatch
):
    deleted = []
    monkeypatch.setattr(graph_api.Config, 'ZEP_API_KEY', 'test-key')
    monkeypatch.setattr(
        graph_api,
        '_delete_cloud_graph_if_present',
        lambda graph_id: deleted.append(graph_id),
    )
    monkeypatch.setattr(graph_api, '_delete_project_evolution_graph', lambda _project: None)

    response = client.delete('/api/graph/delete/graph-literary')

    assert response.status_code == 200
    assert deleted == ['graph-literary']
    remaining = ProjectManager.get_project(project.project_id)
    assert remaining.graph_id == 'graph-personal'
    assert remaining.literary_graph_id is None
    assert remaining.status == ProjectStatus.GRAPH_COMPLETED
