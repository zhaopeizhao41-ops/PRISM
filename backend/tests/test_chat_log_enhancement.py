"""聊天记录解析增强测试（profile_materials.enhance_chat_log）"""

from app.services.profile_materials import (
    enhance_chat_log,
    free_material_to_text,
)

# WeChatMsg 导出格式样例
CHAT_SAMPLE = """2024-01-15 20:30:45 老陈
最近怎么样

2024-01-15 20:31:02 我
还行吧，在纠结要不要辞职

2024-01-15 20:31:30 老陈
啊？怎么突然想辞职

2024-01-15 23:05:10 我
今天又加班到十一点，真的好累啊
有点崩溃，睡不着

2024-01-16 09:12:00 我
早上好！昨晚想通了，先不辞，骑驴找马

2024-01-16 09:15:44 老陈
哈哈聪明
"""

# 无消息头格式的普通文本（日记式）
PLAIN_SAMPLE = """今天想了很多。
工作三年，一直在犹豫要不要换个方向。
晚上和家里通了电话，心里踏实了些。"""


class TestEnhanceChatLog:
    def test_chat_log_gets_summary_appended(self):
        result = enhance_chat_log(CHAT_SAMPLE)
        # 原文保留
        assert "纠结要不要辞职" in result
        # 附加解析摘要
        assert "--- 聊天记录解析摘要" in result
        assert "消息总数: 6" in result
        assert '我方发言识别: 3条（发送者名为"我"）' in result

    def test_scene_tags_and_late_night(self):
        result = enhance_chat_log(CHAT_SAMPLE)
        # "要不要辞职" → 决策类；"好累啊/崩溃" → 情绪类；深夜 23 点
        assert "决策相关1条" in result
        assert "情绪表达1条" in result
        assert "深夜时段1条" in result

    def test_expression_stats_present(self):
        result = enhance_chat_log(CHAT_SAMPLE)
        assert "表达统计:" in result
        assert "高频语气词" in result
        assert "标点:" in result

    def test_self_message_samples_listed(self):
        result = enhance_chat_log(CHAT_SAMPLE)
        assert "我方决策类发言样本:" in result
        assert "我方情绪类发言样本:" in result
        # 样本区（摘要标记之后）只含我方发言，不含对方发言
        summary = result.split("--- 聊天记录解析摘要", 1)[1]
        assert "还行吧，在纠结要不要辞职" in summary
        assert "怎么突然想辞职" not in summary
        assert "哈哈聪明" not in summary

    def test_plain_text_unchanged(self):
        assert enhance_chat_log(PLAIN_SAMPLE) == PLAIN_SAMPLE.strip()

    def test_too_few_messages_unchanged(self):
        short = "2024-01-15 20:30:45 我\n就两三条\n2024-01-15 20:31:02 老陈\n不算聊天记录"
        assert enhance_chat_log(short) == short

    def test_no_self_sender_falls_back_to_all(self):
        log = "\n".join(
            f"2024-01-15 20:3{i}:00 张三\n消息{i}" for i in range(5)
        )
        result = enhance_chat_log(log)
        assert "未能识别" in result
        assert "消息总数: 5" in result

    def test_free_material_to_text_hooks_chat_log(self):
        result = free_material_to_text(CHAT_SAMPLE, "chat_log")
        assert "=== [chat_log" in result
        assert "--- 聊天记录解析摘要" in result

    def test_free_material_to_text_other_types_not_enhanced(self):
        result = free_material_to_text(CHAT_SAMPLE, "diary")
        assert "--- 聊天记录解析摘要" not in result

    def test_multiline_message_content(self):
        log = (
            "2024-01-15 20:30:45 我\n"
            "第一行\n"
            "第二行 谈谈考研的事\n"
            "2024-01-15 20:31:02 老陈\n"
            "回复\n"
            "2024-01-15 20:32:00 我\n"
            "嗯嗯\n"
            "2024-01-15 20:33:00 我\n"
            "又想了想\n"
            "2024-01-15 20:34:00 老陈\n"
            "好\n"
            "2024-01-15 20:35:00 老陈\n"
            "明天聊\n"
        )
        result = enhance_chat_log(log)
        # 多行内容被合并：6 个消息头 → 消息总数 6（而非行数 12）
        assert "消息总数: 6" in result
