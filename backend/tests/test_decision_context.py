"""决策上下文 API 与旧项目兼容性测试。"""

import pytest

from app import create_app
from app.models.project import Project, ProjectManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_create_get_patch_and_list_decision_context(client):
    response = client.post(
        "/api/profile/create",
        json={
            "name": "职业选择",
            "decision_context": {
                "question": "  我该先转行，还是先用副业验证方向？  ",
                "horizon": "one_year",
                "constraints": "  保留六个月现金缓冲。  ",
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    project_id = payload["project_id"]
    expected = {
        "question": "我该先转行，还是先用副业验证方向？",
        "horizon": "one_year",
        "constraints": "保留六个月现金缓冲。",
    }
    assert payload["decision_context"] == expected
    assert ProjectManager.get_project(project_id).decision_context == expected

    fetched = client.get(f"/api/profile/decision-context/{project_id}")
    assert fetched.status_code == 200
    assert fetched.get_json()["data"] == expected

    updated = client.patch(
        f"/api/profile/decision-context/{project_id}",
        json={"question": "是否继续当前工作？", "horizon": "three_months"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"] == {
        "question": "是否继续当前工作？",
        "horizon": "three_months",
        "constraints": "保留六个月现金缓冲。",
    }

    listed = client.get("/api/profile/projects")
    assert listed.status_code == 200
    item = next(row for row in listed.get_json()["data"] if row["project_id"] == project_id)
    assert item["decision_context"] == updated.get_json()["data"]
    assert item["status"] == "ontology_generated"
    assert item["material_count"] == 0
    assert item["total_text_length"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"decision_context": []},
        {"decision_context": {"question": 123}},
        {"decision_context": {"question": "x" * 501}},
        {"decision_context": {"horizon": "x" * 81}},
        {"decision_context": {"constraints": "x" * 1001}},
    ],
)
def test_create_rejects_invalid_decision_context(client, payload):
    response = client.post("/api/profile/create", json=payload)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_create_rejects_non_object_json(client):
    response = client.post("/api/profile/create", json=[])
    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object is required"


def test_patch_rejects_non_object_and_preserves_context(client):
    created = client.post(
        "/api/profile/create",
        json={"decision_context": {"question": "原问题"}},
    )
    project_id = created.get_json()["data"]["project_id"]

    response = client.patch(f"/api/profile/decision-context/{project_id}", json=[])
    assert response.status_code == 400
    assert client.get(f"/api/profile/decision-context/{project_id}").get_json()["data"]["question"] == "原问题"


def test_legacy_project_defaults_to_empty_decision_context():
    project = Project.from_dict(
        {
            "project_id": "proj_legacy",
            "name": "旧项目",
            "status": "created",
            "created_at": "",
            "updated_at": "",
        }
    )
    assert project.decision_context == {"question": "", "horizon": "", "constraints": ""}


def test_project_overview_counts_submitted_materials(client):
    created = client.post("/api/profile/create", json={"name": "资料统计"})
    project_id = created.get_json()["data"]["project_id"]

    submitted = client.post(
        "/api/profile/structured-input",
        json={"project_id": project_id, "form": {"industry": "软件工程"}},
    )
    assert submitted.status_code == 200

    listed = client.get("/api/profile/projects")
    item = next(row for row in listed.get_json()["data"] if row["project_id"] == project_id)
    assert item["material_count"] == 1
    assert item["total_text_length"] > 0
