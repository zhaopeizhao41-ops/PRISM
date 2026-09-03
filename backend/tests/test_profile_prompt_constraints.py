"""画像合成 prompt 约束单测：source 注入 + 长文本证据指引 + 原文节选"""
from app.services.profile_synthesizer import (
    STAGE1_PROMPT,
    _build_system_prompt,
    _raw_text_excerpt,
    _stage1_context,
)


class TestBuildSystemPrompt:
    def test_injects_present_material_types(self):
        prompt = _build_system_prompt([
            {"material_type": "diary", "char_count": 4000},
            {"material_type": "chat_log", "char_count": 2000},
        ])
        assert "本项目实际存在的材料类型只有：chat_log / diary" in prompt
        assert "宁可选 inference" in prompt

    def test_single_type(self):
        prompt = _build_system_prompt([{"material_type": "diary", "char_count": 100}])
        assert "只有：diary" in prompt
        assert "structured_form" not in prompt.split("铁律")[0]  # 头部未列出不存在的类型

    def test_empty_manifest_fallback(self):
        prompt = _build_system_prompt([])
        assert "一律标 inference" in prompt

    def test_fictional_literary_source_is_allowed_when_present(self):
        prompt = _build_system_prompt([{"material_type": "literary", "char_count": 100}])
        assert "literary / inference" in prompt or "inference / literary" in prompt

    def test_iron_rules_preserved(self):
        prompt = _build_system_prompt([{"material_type": "diary", "char_count": 1}])
        for rule in ("只输出一个 JSON", "conflicts 数组", "self_view"):
            assert rule in prompt


class TestStage1EvidenceGuidance:
    def test_expression_dna_accepts_long_form_text(self):
        """纯日记/信件材料也应触发表达基因提取（待办2修复）"""
        assert "第一人称长文本（日记/信件/感想）" in STAGE1_PROMPT
        assert "句式节奏" in STAGE1_PROMPT
        assert "自问自答" in STAGE1_PROMPT

    def test_decision_patterns_accepts_diary_evidence(self):
        assert "日记与信件中记录的过往抉择" in STAGE1_PROMPT


class TestRawTextExcerpt:
    def test_short_text_passthrough(self):
        text = "=== [diary] ===\n今天很好。"
        assert _raw_text_excerpt(text) == text

    def test_long_text_head_tail(self):
        text = "开" * 3000 + "中" * 3000 + "结" * 3000
        excerpt = _raw_text_excerpt(text, limit=1000)
        assert len(excerpt) < 1100
        assert excerpt.startswith("开")
        assert excerpt.endswith("结")
        assert "（中段省略）" in excerpt
        assert "中" not in excerpt.replace("……（中段省略）……", "")

    def test_empty_returns_empty(self):
        assert _raw_text_excerpt(None) == ""
        assert _raw_text_excerpt("   ") == ""


class TestStage1Context:
    def test_appends_excerpt_with_marker(self):
        ctx = _stage1_context("实体上下文", "她说话总用问句。")
        assert ctx.startswith("实体上下文")
        assert "原文节选" in ctx
        assert "她说话总用问句。" in ctx

    def test_no_raw_text_untouched(self):
        assert _stage1_context("实体上下文", None) == "实体上下文"
