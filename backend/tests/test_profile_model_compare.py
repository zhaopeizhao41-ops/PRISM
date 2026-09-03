import json

import pytest

from app import create_app
from app.models.personal_model import PersonalModelStore
from app.models.project import ProjectManager


@pytest.fixture
def profile_project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    project = ProjectManager.create_project('版本比较测试')
    project.project_type = 'personal_profile'
    ProjectManager.save_project(project)
    PersonalModelStore.save(project.project_id, {
        'model_version': 1,
        'current_state': '在职，正在观察新的方向。',
        'basic_info': {'industry': '旅行推销'},
        'personality': {'observed': [{'trait': '谨慎'}]},
        'milestones': [{'summary': '开始记录行动'}],
        'evidence_refs': [{'material_id': 'private', 'quote': '不应出现在差异里'}],
    })
    PersonalModelStore.save(project.project_id, {
        'model_version': 2,
        'current_state': '在职，开始试验新的方向。',
        'basic_info': {'industry': '创作与旅行推销'},
        'personality': {'observed': [{'trait': '谨慎'}, {'trait': '主动'}]},
        'milestones': [{'summary': '开始记录行动'}, {'summary': '完成第一次复盘'}],
        'evidence_refs': [{'material_id': 'private', 'quote': '不应出现在差异里'}],
    })
    return project


@pytest.fixture
def client(profile_project):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_model_version_compare_is_read_only_and_excludes_raw_evidence(client, profile_project):
    response = client.get(
        f'/api/profile/model/compare/{profile_project.project_id}?from=1&to=2'
    )
    assert response.status_code == 200
    payload = response.get_json()['data']
    assert payload['from_version'] == 1
    assert payload['to_version'] == 2
    paths = {item['path'] for item in payload['changes']}
    assert 'current_state' in paths
    assert 'basic_info.industry' in paths
    assert 'personality.observed' in paths
    assert 'milestones' in paths
    assert all('evidence_refs' not in json.dumps(item, ensure_ascii=False) for item in payload['changes'])
    assert PersonalModelStore.get_current(profile_project.project_id)['model_version'] == 2


def test_model_version_compare_defaults_to_previous_and_current(client, profile_project):
    response = client.get(f'/api/profile/model/compare/{profile_project.project_id}')
    assert response.status_code == 200
    assert response.get_json()['data']['from_version'] == 1
    assert response.get_json()['data']['to_version'] == 2


def test_model_version_compare_requires_two_versions(client, profile_project, monkeypatch):
    monkeypatch.setattr(PersonalModelStore, 'list_versions', lambda _project_id: [1])
    response = client.get(f'/api/profile/model/compare/{profile_project.project_id}')
    assert response.status_code == 400


def test_model_version_compare_rejects_unknown_version(client, profile_project):
    response = client.get(
        f'/api/profile/model/compare/{profile_project.project_id}?from=1&to=99'
    )
    assert response.status_code == 404
