"""BranchGenerator 单元测试：mock _chat_json_with_retry，不发起真实 LLM 调用。"""

import pytest

from app.services import branch_generator
from app.services.branch_generator import BranchGenerator


@pytest.fixture
def generator():
    return BranchGenerator(api_key="test-key")


@pytest.fixture
def personal_model():
    return {
        "model_version": "v1",
        "content_hash": "abc123",
        "basic_info": {"age": 35},
        "personality": ["务实"],
        "current_state": "在职工程师",
    }


def test_generate_two_step_flow(generator, personal_model, monkeypatch):
    step1_calls, step2_calls = [], []

    def fake_chat(llm, *, messages, max_tokens):
        # 步骤1（方向穷举）与步骤2（分支展开）用不同 max_tokens 区分
        if max_tokens == 2048:
            step1_calls.append(messages)
            return {
                "selected_directions": [
                    {"archetype": "builder", "positioning": "独立开发", "rationale": "技能匹配"},
                    {"archetype": "scholar", "positioning": "深造转型", "rationale": "知识积累"},
                ]
            }
        step2_calls.append(messages)
        archetype = "builder" if len(step2_calls) == 1 else "scholar"
        return {
            "archetype": archetype,
            "positioning": f"{archetype}定位",
            "timeline": [{"year": "2027", "event": "里程碑"}],
            "key_assumption": "假设成立",
            "day_one": "第一天",
            "first_conflict": "第一个冲突",
        }

    monkeypatch.setattr(branch_generator, "_chat_json_with_retry", fake_chat)

    result = generator.generate(personal_model, branch_count=3)

    assert len(step1_calls) == 1
    assert len(step2_calls) == 2
    assert result["branch_count"] == 2  # 方向数即分支数（不足目标数不硬凑）
    assert [b["archetype"] for b in result["branches"]] == ["builder", "scholar"]
    assert result["source_model_version"] == "v1"
    assert result["source_content_hash"] == "abc123"


def test_generate_backfills_missing_fields(generator, personal_model, monkeypatch):
    """LLM 返回缺字段时由 direction 兜底。"""

    def fake_chat(llm, *, messages, max_tokens):
        if max_tokens == 2048:
            return {"selected_directions": [
                {"archetype": "builder", "positioning": "独立开发", "rationale": "r"},
            ]}
        return {"timeline": []}  # archetype / positioning 均缺失

    monkeypatch.setattr(branch_generator, "_chat_json_with_retry", fake_chat)
    result = generator.generate(personal_model)
    branch = result["branches"][0]
    assert branch["archetype"] == "builder"
    assert branch["positioning"] == "独立开发"
    assert branch["rationale"] == "r"


def test_generate_raises_without_directions(generator, personal_model, monkeypatch):
    monkeypatch.setattr(
        branch_generator, "_chat_json_with_retry",
        lambda llm, *, messages, max_tokens: {"selected_directions": []},
    )
    with pytest.raises(ValueError, match="方向"):
        generator.generate(personal_model)


def test_generate_reports_progress(generator, personal_model, monkeypatch):
    stages = []

    def fake_chat(llm, *, messages, max_tokens):
        if max_tokens == 2048:
            return {"selected_directions": [
                {"archetype": "builder", "positioning": "p", "rationale": "r"},
            ]}
        return {"archetype": "builder", "positioning": "p", "timeline": []}

    monkeypatch.setattr(branch_generator, "_chat_json_with_retry", fake_chat)
    generator.generate(personal_model, progress_callback=lambda s, m: stages.append(s))
    assert "directions" in stages
    assert "expand" in stages
    assert "finalize" in stages
