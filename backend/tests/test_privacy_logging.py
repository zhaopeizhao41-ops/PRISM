import json

from app.utils.logger import summarize_payload


def test_request_log_summary_never_contains_payload_values():
    payload = {
        'project_id': 'proj_private',
        'text': '这是一段不应进入日志的日记正文',
        'llm_api_key': 'sk-secret-value',
        'nested': {'prompt': '个人提示词', 'count': 3},
        'items': ['第一条资料', '第二条资料'],
    }

    summary = summarize_payload(payload)
    serialized = json.dumps(summary, ensure_ascii=False)

    assert 'proj_private' not in serialized
    assert '日记正文' not in serialized
    assert 'sk-secret-value' not in serialized
    assert '个人提示词' not in serialized
    assert summary['text'] == '<redacted>'
    assert summary['llm_api_key'] == '<redacted>'
    assert summary['nested']['prompt'] == '<redacted>'
    assert summary['items'] == '<list len=2>'


def test_request_log_summary_preserves_shape_without_short_values():
    summary = summarize_payload({'name': 'Alice', 'enabled': True, 'count': 2})

    assert summary == {
        'name': '<str len=5>',
        'enabled': '<bool>',
        'count': '<int>',
    }
