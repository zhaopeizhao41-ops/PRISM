from app import create_app
from app.models.project import ProjectManager


def test_demo_project_is_complete_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    first = client.post('/api/profile/demo')
    assert first.status_code == 200
    first_data = first.get_json()['data']
    assert first_data['created'] is True
    project_id = first_data['project_id']

    second = client.post('/api/profile/demo')
    assert second.status_code == 200
    second_data = second.get_json()['data']
    assert second_data['created'] is False
    assert second_data['project_id'] == project_id

    projects = client.get('/api/profile/projects')
    assert projects.status_code == 200
    listed = next(item for item in projects.get_json()['data'] if item['project_id'] == project_id)
    assert listed['is_demo'] is True
    assert listed['model_version'] == 1
    assert listed['branch_count'] == 3
    assert listed['universe_count'] == 2
    assert listed['roundtable_count'] == 1

    model = client.get(f'/api/profile/model/{project_id}')
    assert model.status_code == 200
    assert model.get_json()['data']['model']['traceability']['warnings'] == []

    branches = client.get(f'/api/branch/{project_id}')
    assert branches.status_code == 200
    assert len(branches.get_json()['data']['branches']) == 3

    compare = client.get(f'/api/evolution/compare/{project_id}')
    assert compare.status_code == 200
    assert len(compare.get_json()['data']) == 2

    roundtables = client.get(f'/api/roundtable/list/{project_id}')
    assert roundtables.status_code == 200
    assert roundtables.get_json()['data'][0]['has_moderation'] is True

    action = client.get(f'/api/action/experiments/{project_id}')
    assert action.status_code == 200
    assert len(action.get_json()['data']) == 1

    # The demo remains local-only: attempting a new cloud-backed branch run
    # is rejected by the same consent contract as a fresh user project.
    blocked = client.post('/api/branch/generate', json={'project_id': project_id})
    assert blocked.status_code == 428
    assert blocked.get_json()['code'] == 'cloud_processing_consent_required'
