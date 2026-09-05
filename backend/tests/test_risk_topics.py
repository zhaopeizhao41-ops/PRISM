import pytest

from app import create_app
from app.models.project import ProjectManager
from app.utils.risk import detect_risk_topics


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("我该如何安排贷款和现金流？", ["finance"]),
        ("这个症状是否需要去看医生？", ["health"]),
        ("合同纠纷是否应该咨询律师？", ["legal"]),
        ("我想换一个城市生活。", []),
        ("Should I invest while managing a medical treatment contract?", ["finance", "health", "legal"]),
    ],
)
def test_detect_risk_topics_is_conservative_and_stable(text, expected):
    assert detect_risk_topics(text) == expected


def test_profile_project_overview_exposes_risk_topics(client):
    response = client.post(
        "/api/profile/create",
        json={"name": "风险提醒", "decision_context": {"question": "我该不该贷款转行？"}},
    )
    assert response.status_code == 200
    project_id = response.get_json()["data"]["project_id"]

    listed = client.get("/api/profile/projects")
    assert listed.status_code == 200
    item = next(row for row in listed.get_json()["data"] if row["project_id"] == project_id)
    assert item["risk_topics"] == ["finance"]
