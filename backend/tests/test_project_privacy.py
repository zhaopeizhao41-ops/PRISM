from datetime import datetime, timedelta, timezone
import json

import pytest
from flask import Flask

from app import create_app
from app.api import graph as graph_api
from app.models.project import ProjectManager, ProjectStatus
from app.utils.privacy import has_cloud_processing_consent, is_retention_expired, purge_expired_projects


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    item = ProjectManager.create_project('隐私设置测试')
    item.project_type = 'personal_profile'
    item.ontology = {'entity_types': [], 'edge_types': []}
    ProjectManager.save_project(item)
    return item


@pytest.fixture
def client(project):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_new_project_requires_cloud_consent_for_build(client, project):
    response = client.post('/api/profile/build', json={'project_id': project.project_id})

    assert response.status_code == 428
    assert response.get_json()['code'] == 'cloud_processing_consent_required'
    assert has_cloud_processing_consent(ProjectManager.get_project(project.project_id)) is False


def test_privacy_patch_grants_consent_and_sets_retention(client, project):
    response = client.patch(
        f'/api/profile/privacy/{project.project_id}',
        json={'cloud_processing_consent': True, 'retention_days': 90},
    )

    assert response.status_code == 200
    settings = response.get_json()['data']
    assert settings['cloud_processing_consent'] is True
    assert settings['retention_days'] == 90
    saved = ProjectManager.get_project(project.project_id)
    assert saved.privacy_settings['consent_source'] == 'user_settings'


def test_revoking_consent_purges_all_cloud_references(client, project, monkeypatch):
    project.privacy_settings.update({
        'cloud_processing_consent': True,
        'consent_source': 'user_settings',
    })
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = 'personal'
    project.literary_graph_id = 'literary'
    project.evolution_graph_id = 'evolution'
    ProjectManager.save_project(project)
    deleted = []
    monkeypatch.setattr(
        graph_api,
        '_delete_project_cloud_graphs',
        lambda item: deleted.extend([item.graph_id, item.literary_graph_id]),
    )
    monkeypatch.setattr(graph_api, '_delete_project_evolution_graph', lambda item: setattr(item, 'evolution_graph_id', None))

    response = client.patch(
        f'/api/profile/privacy/{project.project_id}',
        json={'cloud_processing_consent': False},
    )

    assert response.status_code == 200
    assert deleted == ['personal', 'literary']
    saved = ProjectManager.get_project(project.project_id)
    assert saved.privacy_settings['cloud_processing_consent'] is False
    assert saved.graph_id is None
    assert saved.literary_graph_id is None
    assert saved.evolution_graph_id is None
    assert saved.status == ProjectStatus.ONTOLOGY_GENERATED


def test_retention_expiry_uses_updated_at_and_explicit_days(project):
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    project.updated_at = (now - timedelta(days=31)).isoformat()
    project.privacy_settings['retention_days'] = 30
    assert is_retention_expired(project, now=now) is True
    project.privacy_settings['retention_days'] = None
    assert is_retention_expired(project, now=now) is False


def test_create_profile_rejects_non_boolean_consent(client):
    response = client.post('/api/profile/create', json={
        'name': 'bad',
        'cloud_processing_consent': 'yes',
    })

    assert response.status_code == 400


def test_startup_purges_expired_local_project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    item = ProjectManager.create_project('过期项目')
    item.project_type = 'personal_profile'
    item.privacy_settings['retention_days'] = 30
    ProjectManager.save_project(item)
    meta_path = ProjectManager._get_project_meta_path(item.project_id)
    with open(meta_path, 'r', encoding='utf-8') as handle:
        metadata = json.load(handle)
    metadata['updated_at'] = '2020-01-01T00:00:00'
    with open(meta_path, 'w', encoding='utf-8') as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'

    deleted = purge_expired_projects(
        app,
        now=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    assert item.project_id in deleted
    assert ProjectManager.get_project(item.project_id) is None
