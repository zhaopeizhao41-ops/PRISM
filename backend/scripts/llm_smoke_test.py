"""
LLM 写作链路真实调用冒烟测试（手动运行，产生 API 费用，不入 pytest 套件）
用《狂人日记》人设验证三个写作点：
  1. 圆桌宇宙发言（voice matching + SPEECH_STYLE_RULES）
  2. 推演叙事（ADVANCE_PROMPT 风格 + NARRATIVE_STYLE_RULES）
  3. chat_json（主持人 summary 风格的 JSON 输出）
自动检测 AI 腔指标（禁用词命中率）。
用法: uv run python scripts/llm_smoke_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from app.services.writing_style import (
    NARRATIVE_STYLE_RULES,
    SPEECH_STYLE_RULES,
    SUMMARY_STYLE_RULES,
    voice_block,
)
from app.utils.llm_client import LLMClient

# AI 腔禁用词表（writing_style 的反向检测）
AI_TELLS = [
    "值得注意", "总而言之", "在这个过程中", "无疑", "某种意义上", "仿佛在诉说",
    "标志着", "开启了新篇章", "重要转折点", "见证着", "诠释了", "彰显了",
    "埋下了伏笔", "人生就是一场", "选择比努力更重要",
]

expression_dna = [
    {"feature": "口头禅：用『我想：』引出推论，从不说'因为'", "scene": "议论",
     "example": "我想：我同赵贵翁有什么仇", "source": "diary"},
    {"feature": "标点习惯：连续问句收尾，反问不作答", "scene": "对话",
     "example": "从来如此，便对么？", "source": "chat_log"},
    {"feature": "情绪低时省略号收尾，话说一半", "scene": "深夜独白",
     "example": "救救孩子……", "source": "diary"},
]

persona = {
    "basic_info": {"name": "狂人", "age": 30, "occupation": "候补官员（养病在家）"},
    "personality": {"self_view": "多疑、敏感、逻辑严密", "observed": "周围人认为他疯了"},
    "current_state": "怀疑所有人要吃人，精神紧绷但思维极度清醒",
}

voice = voice_block(expression_dna)

universe_system = f"""你是一个人在某个平行宇宙中的"自己"。你正在参加一场特殊的圆桌。

你的人格底座（所有宇宙共有的你）：
{json.dumps(persona, ensure_ascii=False)}

你所在的宇宙：你选择了「辞官养病、专心著述」这条分支，目前推演到第二阶段（第2/6阶段）。

你在本宇宙的亲身经历：
- 辞了官，搬回老宅，靠积蓄过活；大哥隔三差五来劝我回去
- 半年来写了几万字札记，越写越觉得二十年来只看了两个字

{voice}

{SPEECH_STYLE_RULES}

规则：
1. 用第一人称"我"发言，像真人说话，不要列条目、不要小标题
2. 你的立场必须来自你亲身经历的事，不是抽象推理
3. 发言 150~300 字，只输出发言内容本身，不要任何前缀"""

ISSUE = "议题：要不要接受家里的安排，回去做官？"

narrative_user = f"""你是一个人生推演引擎。对下面这个人物推进一个阶段（第3阶段/共6阶段，主题：坐吃山空）：

人物：狂人，30岁，辞官半年，积蓄还够14个月，靠写札记度日，大哥多次上门劝其回衙门
上一状态：职业=无业著述；家庭=与大哥关系紧张；资源=积蓄14个月；心理=清醒但紧绷
约束：本阶段积蓄要减少；大哥必须出场；不可控事件：老宅隔壁搬来一户新邻居

只输出一个 JSON 对象，包含：
- occurred_events: 本阶段发生的 3-5 件事（每件一句话）
- state_snapshot: 150 字以内的本阶段叙事

{NARRATIVE_STYLE_RULES}"""

moderator_user = f"""你是圆桌主持人。桌上两个宇宙自我围绕"要不要回去做官"争吵：
宇宙A（回去做官的）：拿了俸禄，饭碗稳了，但每天要应酬看不惯的人，札记停写了。
宇宙B（继续著述的）：写到一半积蓄告急，大哥翻脸，开始典当东西。

{SUMMARY_STYLE_RULES}

只输出一个 JSON 对象：{{"summary": "一句话说清本轮最大分歧", "divergence": "两条路的根本差异点"}}"""


def ai_tell_hits(text: str):
    return [t for t in AI_TELLS if t in text]


def main():
    client = LLMClient()
    print(f"模型: {client.model} @ {client.base_url}\n")

    # ---- 1. 宇宙发言 ----
    print("=" * 60)
    print("[1] 圆桌宇宙发言（voice matching + 发言文风）")
    speech = client.chat(
        [{"role": "system", "content": universe_system},
         {"role": "user", "content": ISSUE}],
        temperature=0.8, max_tokens=600,
    )
    print(speech)
    hits = ai_tell_hits(speech)
    print(f"\n-- AI 腔命中: {hits or '无'} | 长度: {len(speech)}字 | "
          f"『我想：』出现: {'我想：' in speech} | 问句: {'？' in speech}")

    # ---- 2. 推演叙事 ----
    print("\n" + "=" * 60)
    print("[2] 推演叙事（occurred_events + state_snapshot）")
    result = client.chat_json(
        [{"role": "user", "content": narrative_user}],
        temperature=0.5, max_tokens=1200,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    events_text = " ".join(result.get("occurred_events") or [])
    snapshot = result.get("state_snapshot") or ""
    hits2 = ai_tell_hits(events_text + snapshot)
    print(f"-- AI 腔命中: {hits2 or '无'} | 事件数: {len(result.get('occurred_events') or [])} | "
          f"snapshot长度: {len(snapshot)}")

    # ---- 3. 主持人 JSON ----
    print("\n" + "=" * 60)
    print("[3] 主持人总结（JSON 模式）")
    mod = client.chat_json(
        [{"role": "user", "content": moderator_user}],
        temperature=0.3, max_tokens=500,
    )
    print(json.dumps(mod, ensure_ascii=False, indent=2))
    hits3 = ai_tell_hits(mod.get("summary", ""))
    print(f"-- AI 腔命中: {hits3 or '无'}")

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    all_hits = hits + hits2 + hits3
    if all_hits:
        print(f"⚠ 存在 AI 腔残留: {all_hits}")
    else:
        print("✓ 三个写作点均未命中 AI 腔禁用词")


if __name__ == "__main__":
    main()
