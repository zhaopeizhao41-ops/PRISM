from datetime import date, timedelta

import pytest

from app import create_app
from app.models.action_experiment import ActionExperimentStore
from app.models.project import ProjectManager


@pytest.fixture
def profile_project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    project = ProjectManager.create_project('行动实验测试')
    project.project_type = 'personal_profile'
    ProjectManager.save_project(project)
    return project


@pytest.fixture
def client(profile_project):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _payload(project_id, **overrides):
    payload = {
        'project_id': project_id,
        'title': '每周安排两个无会议时段',
        'horizon_days': 30,
        'goal': '减少工作切换，恢复稳定创作时间。',
        'minimum_action': '本周先锁定两个 90 分钟无会议时段。',
        'success_metric': '至少完成 4 个无会议时段，并记录实际完成率。',
        'stop_condition': '连续两周影响必要交付时暂停并复盘。',
        'expected_cost': '每周提前协调约 30 分钟。',
        'review_date': (date.today() + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_create_list_update_and_retrofit_experiment(client, profile_project):
    response = client.post('/api/action/experiments', json=_payload(profile_project.project_id))
    assert response.status_code == 201
    experiment = response.get_json()['data']
    assert experiment['status'] == 'planned'
    assert experiment['horizon_days'] == 30
    assert experiment['retrospective'] is None

    listed = client.get(f"/api/action/experiments/{profile_project.project_id}")
    assert listed.status_code == 200
    assert [item['experiment_id'] for item in listed.get_json()['data']] == [experiment['experiment_id']]

    updated = client.patch(
        f"/api/action/experiments/{experiment['experiment_id']}",
        json={'project_id': profile_project.project_id, 'status': 'in_progress'},
    )
    assert updated.status_code == 200
    assert updated.get_json()['data']['status'] == 'in_progress'

    retrospective = client.post(
        f"/api/action/experiments/{experiment['experiment_id']}/retrospective",
        json={
            'project_id': profile_project.project_id,
            'outcome': 'partial',
            'variance_type': 'execution_deviation',
            'observed_result': '完成了 3 个时段，临时会议占用了另一个。',
            'notes': '下轮提前一天确认会议变更。',
            'model_update_consent': True,
        },
    )
    assert retrospective.status_code == 200
    saved = retrospective.get_json()['data']
    assert saved['retrospective']['outcome'] == 'partial'
    assert saved['retrospective']['model_update_consent'] is True
    assert saved['retrospective']['model_update_status'] == 'awaiting_explicit_model_action'
    assert saved['retrospective']['reviewed_at'] == date.today().isoformat()

    # A retrospective records consent only; it does not mutate the profile model.
    assert ActionExperimentStore.get(profile_project.project_id, experiment['experiment_id'])['retrospective']


@pytest.mark.parametrize('field,value', [
    ('horizon_days', 14),
    ('review_date', 'not-a-date'),
    ('title', ''),
])
def test_create_rejects_invalid_contract(client, profile_project, field, value):
    response = client.post(
        '/api/action/experiments',
        json=_payload(profile_project.project_id, **{field: value}),
    )
    assert response.status_code == 400
    assert response.get_json()['success'] is False


def test_source_session_must_belong_to_project(client, profile_project):
    response = client.post(
        '/api/action/experiments',
        json=_payload(profile_project.project_id, source_session_id='evo_missing'),
    )
    assert response.status_code == 400
    assert 'source_session_id' in response.get_json()['error']


def test_retrofit_requires_explicit_allowed_values(client, profile_project):
    created = client.post('/api/action/experiments', json=_payload(profile_project.project_id))
    experiment_id = created.get_json()['data']['experiment_id']
    response = client.post(
        f'/api/action/experiments/{experiment_id}/retrospective',
        json={
            'project_id': profile_project.project_id,
            'outcome': 'unknown',
            'observed_result': '暂时没有记录',
        },
    )
    assert response.status_code == 400


def test_completed_experiment_is_terminal(client, profile_project):
    created = client.post('/api/action/experiments', json=_payload(profile_project.project_id))
    experiment_id = created.get_json()['data']['experiment_id']
    started = client.patch(
        f'/api/action/experiments/{experiment_id}',
        json={'project_id': profile_project.project_id, 'status': 'in_progress'},
    )
    assert started.status_code == 200
    completed = client.patch(
        f'/api/action/experiments/{experiment_id}',
        json={'project_id': profile_project.project_id, 'status': 'completed'},
    )
    assert completed.status_code == 200
    reopened = client.patch(
        f'/api/action/experiments/{experiment_id}',
        json={'project_id': profile_project.project_id, 'status': 'in_progress'},
    )
    assert reopened.status_code == 409
    assert 'completed -> in_progress' in reopened.get_json()['error']


def test_delete_experiment(client, profile_project):
    created = client.post('/api/action/experiments', json=_payload(profile_project.project_id))
    experiment_id = created.get_json()['data']['experiment_id']
    deleted = client.delete(
        f'/api/action/experiments/{experiment_id}',
        json={'project_id': profile_project.project_id},
    )
    assert deleted.status_code == 200
    assert deleted.get_json()['success'] is True
    assert client.get(f'/api/action/experiments/{profile_project.project_id}').get_json()['data'] == []
