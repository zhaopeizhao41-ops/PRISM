"""《狂人日记》（鲁迅，公有领域，维基文库）真实语料集成测试
覆盖确定性管线：材料预处理 → 聊天解析增强 → 表达基因渲染 → 文风模块 → 合并/指纹
不调 LLM、不连 Zep（推演/蒸馏的 prompt 组装由各自单测覆盖）
"""
from pathlib import Path

import pytest

from app.services.profile_materials import (
    enhance_chat_log,
    free_material_to_text,
    material_fingerprint,
    merge_materials,
)
from app.services.writing_style import (
    NARRATIVE_STYLE_RULES,
    SPEECH_STYLE_RULES,
    SUMMARY_STYLE_RULES,
    voice_block,
)

FIXTURE = Path(__file__).parent / "fixtures" / "kuangren_riji.txt"

# 用小说人物拼的 WeChatMsg 格式聊天记录（含深夜发言与情绪表达）
CHAT = """1918-04-02 20:30:45 我
今天晚上，很好的月光。可是须十分小心，赵家的狗看我两眼呢

1918-04-02 20:32:10 大哥
你又在想些什么？赶紧吃药罢

1918-04-02 20:33:02 我
我想：同赵贵翁有什么仇？只有廿年前踹了古久先生的流水簿子

1918-04-03 01:15:33 我
睡不着，总是睡不着。这历史没有年代，歪歪斜斜每页都写着仁义道德

1918-04-03 08:40:12 陈老五
先生，今天鱼的眼睛白而且硬，张着嘴么

1918-04-03 09:02:55 我
从来如此，便对么？！

1918-04-03 09:05:30 大哥
疯子有什么好看！

1918-04-04 23:50:18 我
没有吃过人的孩子，或者还有？救救孩子……
"""


@pytest.fixture(scope="module")
def novel_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class TestNovelAsDiary:
    def test_confidence_header_and_passthrough(self, novel_text):
        block = free_material_to_text(novel_text, "diary", time_range="1918")
        assert block.startswith(
            "=== [diary | 来源: 用户提交 | 时间范围: 1918 | 置信度: 0.6] ==="
        )
        assert "很好的月光" in block
        # 日记体不是聊天记录格式 → 不触发解析摘要（原文直通）
        assert "--- 聊天记录解析摘要" not in block

    def test_full_text_extracted(self, novel_text):
        assert "救救孩子" in novel_text  # 结尾
        assert "【一】" in novel_text and "【十三】" in novel_text  # 章节


class TestNovelAsChatLog:
    def test_self_speaker_and_late_night(self):
        enhanced = enhance_chat_log(CHAT)
        assert "消息总数: 8" in enhanced
        assert '我方发言识别: 5条（发送者名为"我"）' in enhanced
        assert "深夜时段2条" in enhanced  # 01:15 与 23:50
        assert "情绪表达1条" in enhanced  # "睡不着，总是睡不着"
        assert "表达统计:" in enhanced and "高频语气词" in enhanced
        # 摘要样本区不含对方发言
        summary = enhanced.split("--- 聊天记录解析摘要", 1)[1]
        assert "赶紧吃药罢" not in summary

    def test_piped_through_materials(self):
        block = free_material_to_text(CHAT, "chat_log")
        assert "=== [chat_log" in block
        assert "--- 聊天记录解析摘要" in block


class TestVoiceMatching:
    def test_voice_block_renders_dna(self):
        dna = [
            {"feature": "口头禅：从不说'因为'，只用'我想：'引出推论", "scene": "议论",
             "example": "我想：我同赵贵翁有什么仇", "source": "diary"},
            {"feature": "标点习惯：连续问句收尾，反问不作答", "scene": "对话",
             "example": "从来如此，便对么？", "source": "chat_log"},
            {"feature": "情绪低时省略号收尾，话说一半", "scene": "深夜独白",
             "example": "救救孩子……", "source": "diary"},
        ]
        vb = voice_block(dna)
        assert "你说话要像TA本人" in vb
        assert '例："从来如此，便对么？"' in vb

    def test_empty_dna_no_injection(self):
        assert voice_block([]) == ""
        assert voice_block([{"feature": ""}]) == ""


class TestStyleModulesReady:
    def test_three_rule_sets_loaded(self):
        for rules in (SPEECH_STYLE_RULES, NARRATIVE_STYLE_RULES, SUMMARY_STYLE_RULES):
            assert len(rules) > 50


class TestMergeAndFingerprint:
    def test_merge_and_fingerprint(self, novel_text):
        blocks = [
            free_material_to_text(novel_text, "diary"),
            free_material_to_text(CHAT, "chat_log"),
        ]
        merged = merge_materials(blocks)
        assert merged.count("=== [") == 2
        fp1 = material_fingerprint(merged)
        assert len(fp1) == 16
        assert fp1 != material_fingerprint(merged + " ")
