import json

import pytest

from app import create_app
from app.api.profile import _save_manifest
from app.models.personal_model import PersonalModelStore
from app.models.project import ProjectManager


@pytest.fixture
def export_project(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(tmp_path / 'projects'))
    project = ProjectManager.create_project('导出隐私测试')
    project.project_type = 'personal_profile'
    project.files = [{'filename': 'diary.txt', 'path': '/private/path/diary.txt', 'size': 12}]
    ProjectManager.save_project(project)
    _save_manifest(project.project_id, [{
        'material_id': 'mat_private',
        'material_type': 'diary',
        'material_mode': 'personal',
        'schema_version': 2,
        'fingerprint': 'fp',
        'char_count': 12,
        'normalized_text': '这是不应默认导出的原始正文。',
        'chunks': [{'chunk_id': 'chunk_1', 'text': '原文引用'}],
        'goals': ['完成测试'],
    }])
    ProjectManager.save_extracted_text(project.project_id, '完整提取正文')
    PersonalModelStore.save(project.project_id, {
        'model_version': 1,
        'current_state': '测试中',
        'evidence_refs': [{'material_id': 'mat_private', 'quote': '原文引用'}],
        'expression_dna': [{'feature': '句式', 'example': '另一段原文摘录'}],
        'llm_api_key': 'should-never-export',
    })
    return project


@pytest.fixture
def client(export_project):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _payload(response):
    assert response.status_code == 200
    return json.loads(response.data.decode('utf-8'))


def test_export_defaults_to_metadata_without_raw_materials(client, export_project):
    response = client.get(f'/api/profile/export/{export_project.project_id}')
    assert response.headers['Cache-Control'] == 'no-store'
    payload = _payload(response)

    assert payload['privacy']['includes_raw_materials'] is False
    assert payload['materials'][0]['has_text'] is True
    assert 'normalized_text' not in payload['materials'][0]
    assert 'extracted_text' not in payload
    serialized = json.dumps(payload, ensure_ascii=False)
    assert '完整提取正文' not in serialized
    assert '原文引用' not in payload['personal_model'].get('evidence_refs', [{}])[0].get('quote', '')
    assert 'example' not in payload['personal_model']['expression_dna'][0]
    assert all('text' not in chunk for chunk in payload['materials'][0].get('chunks', []))
    assert '/private/path' not in serialized
    assert 'should-never-export' not in serialized


def test_export_includes_raw_materials_only_when_explicitly_requested(client, export_project):
    payload = _payload(client.get(
        f'/api/profile/export/{export_project.project_id}?include_raw=true'
    ))

    assert payload['privacy']['includes_raw_materials'] is True
    assert payload['materials'][0]['normalized_text'] == '这是不应默认导出的原始正文。'
    assert payload['extracted_text'] == '完整提取正文'
    assert payload['materials'][0]['chunks'][0]['text'] == '原文引用'
    assert payload['personal_model']['expression_dna'][0]['example'] == '另一段原文摘录'
    serialized = json.dumps(payload, ensure_ascii=False)
    assert 'should-never-export' not in serialized
    assert '/private/path' not in serialized
