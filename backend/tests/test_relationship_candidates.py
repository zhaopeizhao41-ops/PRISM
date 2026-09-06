"""RelationshipAgentGenerator.list_candidates 单元测试：mock ZepEntityReader，不发真实请求。

覆盖 self 判定三信号防御（Zep relation_kind=self 分块归一化噪声场景）：
1. 硬名单（我/the speaker/the User 等叙述者代称）→ 始终排除；
2. summary 叙述者标识词（"The narrator, 涓生"）→ 排除，画像豁免无效；
3. rk=self 且画像未列为关系人 → 排除；
4. rk=self 但画像列为关系人且无叙述者标识 → Zep 误标被画像纠正，保留（graph_grounded + 真实事实）；
5. 补充路径不引入图谱 self 节点（画像漂移防御），但误标且事实不足者允许 profile_only 补充。

覆盖噪声过滤（Zep 把物品/被谈论第三方错标为 Person）：
6. 单字 CJK 物品与纯谈论第三方（中英文谈论/画像词、大小写不敏感）被过滤；
7. 混合事实与真实互动者保留；无有效事实不判噪声；
8. 已知权衡：「与TA谈论X」句式的事实同样命中谈论模式，纯谈话句式的真人会被误判；
9. 画像列为关系人的图谱噪声实体经 profile_only 路径恢复（图谱激进去噪的逃生通道）。
"""

from typing import Any, Dict, List

import pytest

from app.services import relationship_agent_generator as rag
from app.services.zep_entity_reader import EntityNode, FilteredEntities


def _person(name: str, relation_kind=None, facts=None, summary=None) -> EntityNode:
    attrs: Dict[str, Any] = {"name": name}
    if relation_kind is not None:
        attrs["relation_kind"] = relation_kind
    return EntityNode(
        uuid=f"uuid-{name}",
        name=name,
        labels=["Person"],
        summary=summary if summary is not None else f"{name}的摘要",
        attributes=attrs,
        related_edges=[{"fact": f} for f in (facts or [])],
    )


def _install_graph(monkeypatch, entities: List[EntityNode]):
    class FakeReader:
        def filter_defined_entities(self, **kwargs):
            return FilteredEntities(entities=entities, entity_types={"Person"},
                                    total_count=len(entities), filtered_count=len(entities))

    monkeypatch.setattr(rag.RelationshipAgentGenerator, "__init__",
                        lambda self, api_key=None: setattr(self, "reader", FakeReader()))


def _model(rels=None):
    return {"relationships": rels or []}


def test_hard_names_excluded(monkeypatch):
    """叙述者代称硬名单（含英文别名）无论 rk 如何一律排除。"""
    _install_graph(monkeypatch, [
        _person("the speaker", None, ["f1", "f2"]),
        _person("the User", "self", ["f1", "f2"]),
        _person("我", "self", ["f1", "f2"]),
        _person("阿随", "other", ["子君 feeds 阿随", "阿随 left 吉兆胡同"]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert names == ["阿随"]


def test_narrator_marker_overrides_profile(monkeypatch):
    """summary 含叙述者标识（"The narrator, 涓生"）→ 即使画像列为关系人也排除。"""
    _install_graph(monkeypatch, [
        _person("涓生", "self", ["涓生 suddenly thought of 子君's death", "f2"],
                summary="The narrator, 涓生, felt that while unexpected events were anticipated."),
    ])
    model = _model(rels=[{"person": "涓生", "relation": "丈夫", "closeness": "close", "influence": "漂移产物"}])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", model)]
    assert "涓生" not in names


def test_self_mark_excluded_without_profile_support(monkeypatch):
    """rk=self 且画像未列为关系人 → 排除（叙述者别名涓生/史涓生）。"""
    _install_graph(monkeypatch, [
        _person("涓生", "self", ["涓生 suddenly thought of 子君's death", "f2"] * 2),
        _person("史涓生", "self", ["史涓生 received a notice", "f2"] * 2),
        _person("小官太太", "other", ["太太 mocked us", "f2"]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert "涓生" not in names
    assert "史涓生" not in names
    assert "小官太太" in names


def test_self_mislabel_recovered_by_profile(monkeypatch):
    """rk=self、无叙述者标识、画像列为关系人 → Zep 误标被画像纠正，保留并使用真实图谱事实。"""
    _install_graph(monkeypatch, [
        _person("子君", "self", [f"子君 fact {i}" for i in range(6)],
                summary="子君曾与涓生在吉兆胡同共同生活，她不仅操持家务。"),
        _person("阿随", "other", [f"阿随 fact {i}" for i in range(3)]),
    ])
    model = _model(rels=[{"person": "子君", "relation": "恋人", "closeness": "close", "influence": "最深"}])
    gen = rag.RelationshipAgentGenerator()
    cands = {c["person_name"]: c for c in gen.list_candidates("g", model)}
    assert "子君" in cands
    zijun = cands["子君"]
    assert zijun["provenance"] == "graph_grounded"
    assert zijun["mediated_only"] is False
    assert zijun["fact_count"] == 6
    assert zijun["relation_note"] == "恋人"


def test_supplement_skips_graph_self_nodes(monkeypatch):
    """补充路径：画像把图谱 self 节点（含叙述者标识）列为关系人 → 不引入；纯画像人物正常补充。"""
    _install_graph(monkeypatch, [
        _person("涓生", "self", ["涓生 f1", "f2"],
                summary="The narrator, 涓生, felt something."),
        _person("阿随", "other", ["阿随 f1", "f2"]),
    ])
    model = _model(rels=[
        {"person": "涓生", "relation": "丈夫", "closeness": "close", "influence": "漂移产物"},
        {"person": "官太太", "relation": "邻居", "closeness": "distant", "influence": "轻"},
    ])
    gen = rag.RelationshipAgentGenerator()
    cands = {c["person_name"]: c for c in gen.list_candidates("g", model)}
    # 涓生：graph 路径排除（叙述者标识）+ 补充路径排除 → 不出现
    assert "涓生" not in cands
    # 官太太：不在图谱 → profile_only 补充
    assert cands["官太太"]["provenance"] == "profile_only"
    assert cands["官太太"]["mediated_only"] is True


def test_supplement_adds_profile_only_person(monkeypatch):
    """补充路径：画像中不在图谱的人正常进入候选（profile_only）。"""
    _install_graph(monkeypatch, [
        _person("阿随", "other", ["阿随 f1", "f2"]),
    ])
    model = _model(rels=[{"person": "子君", "relation": "恋人", "closeness": "close", "influence": "影响"}])
    gen = rag.RelationshipAgentGenerator()
    cands = {c["person_name"]: c for c in gen.list_candidates("g", model)}
    assert "子君" in cands and cands["子君"]["provenance"] == "profile_only"


def test_mislabel_with_few_facts_supplemented_as_profile_only(monkeypatch):
    """误标 self、画像列为关系人但图谱事实不足 → graph 路径不进，补充路径以 profile_only 兜底。"""
    _install_graph(monkeypatch, [
        _person("子君", "self", ["仅一条事实"],
                summary="子君曾与涓生在吉兆胡同共同生活。"),
    ])
    model = _model(rels=[{"person": "子君", "relation": "恋人", "closeness": "close", "influence": "影响"}])
    gen = rag.RelationshipAgentGenerator()
    cands = {c["person_name"]: c for c in gen.list_candidates("g", model)}
    assert "子君" in cands
    assert cands["子君"]["provenance"] == "profile_only"


# ---------- 噪声候选过滤（Zep 把物品/被谈论第三方错标为 Person） ----------

def test_single_char_object_filtered(monkeypatch):
    """单字 CJK 名（书/信）→ 物品误标，过滤；两字名不受影响。"""
    _install_graph(monkeypatch, [
        _person("书", "other", ["I found nothing to read in the library.", "They were playing with a child."]),
        _person("阿随", "other", ["I released Ah Sui.", "子君 feeds 阿随."]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert "书" not in names
    assert "阿随" in names


def test_mention_only_figure_filtered(monkeypatch):
    """全部事实均为谈论/画像类 → 被谈论的第三方（雪莱/泰戈尔），过滤。"""
    _install_graph(monkeypatch, [
        _person("雪莱", "other", [
            "The speaker discusses Shelley.",
            "A portrait of Shelley was pinned on the wall.",
            "I discussed雪莱 with 子君.",
        ]),
        _person("泰戈尔", "other", [
            "The speaker discussed Tagore with Zijun.",
            "The speaker discusses Tagore.",
        ]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert "雪莱" not in names
    assert "泰戈尔" not in names


def test_mixed_facts_person_kept(monkeypatch):
    """谈论事实 + 真实互动事实混合 → 保留（有直接互动即非纯谈论）。"""
    _install_graph(monkeypatch, [
        _person("世交", "other", [
            "The speaker discussed the family friend.",
            "The family friend told me coldly that I could not stay there.",
        ]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert names == ["世交"]


def test_real_interactant_not_hurt_by_mention_patterns(monkeypatch):
    """真实互动人物（官太太 informed the narrator / 主人 rented）不被谈论词误伤。"""
    _install_graph(monkeypatch, [
        _person("官太太", "other", [
            "The official's wife informed the narrator that Zijun's father had come.",
            "Zijun was taken away by her father.",
        ]),
        _person("主人", "other", [
            "The owner rented the two south rooms.",
            "The owner is married to the夫人.",
        ]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert set(names) == {"官太太", "主人"}


# ---------- 噪声过滤细化：模式全族覆盖 / 边界 / 已知权衡 ----------

def test_noise_each_english_mention_verb_family(monkeypatch):
    """每个英文谈论动词族（discuss/mention/talked about/talks about/spoke of）单独成立即可判 mention_only。"""
    _install_graph(monkeypatch, [
        _person("黑格尔", "other", ["The speaker discusses Hegel.", "We discussed Hegel at dinner."]),
        _person("康德", "other", ["I mentioned Kant in my letter.", "Kant was mentioned twice."]),
        _person("叔本华", "other", ["We talked about Schopenhauer last night.", "They talked about him often."]),
        _person("尼采", "other", ["She talks about Nietzsche constantly.", "He talks about him with everyone."]),
        _person("萨特", "other", ["He spoke of Sartre yesterday.", "She often spoke of Sartre."]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert names == []


def test_noise_chinese_mention_and_portrait_patterns(monkeypatch):
    """中文谈论词（谈论/谈到/提到/说起）与画像词（半身像/照片）全量命中 → 过滤。"""
    _install_graph(monkeypatch, [
        _person("鲁迅", "other", ["我常常谈论鲁迅", "聚会时谈到过鲁迅"]),
        _person("胡适", "other", ["日记里提到过胡适", "说起过胡适的名字"]),
        _person("周作人", "other", ["杂志上有他的半身像", "书里夹着他的照片"]),
    ])
    gen = rag.RelationshipAgentGenerator()
    names = [c["person_name"] for c in gen.list_candidates("g", _model())]
    assert names == []


def test_noise_mention_patterns_case_insensitive(monkeypatch):
    """谈论动词大小写不敏感（DISCUSSES / Talked About 仍命中）。"""
    _install_graph(monkeypatch, [
        _person("易卜生", "other", ["The Speaker DISCUSSES Ibsen.", "We Talked About Ibsen."]),
    ])
    gen = rag.RelationshipAgentGenerator()
    assert [c["person_name"] for c in gen.list_candidates("g", _model())] == []


def test_noise_single_char_boundary_rules():
    """单字规则边界：CJK 单字（简/繁、含首尾空白）→ 物品；英文字母与假名单字 → 不适用（交由事实判定）。"""
    assert rag._is_noise_entity(_person("书", "other", ["f1", "f2"])) == "single_char_object"
    assert rag._is_noise_entity(_person("信", "other", ["f1"])) == "single_char_object"
    assert rag._is_noise_entity(_person("貓", "other", [])) == "single_char_object"   # 繁体仍在 CJK 统一表意区间
    assert rag._is_noise_entity(_person(" 书 ", "other", ["f1"])) == "single_char_object"  # 首尾空白先剥离
    assert rag._is_noise_entity(_person("A", "other", ["f1", "f2"])) is None   # 英文单字不适用单字规则
    assert rag._is_noise_entity(_person("ね", "other", ["f1", "f2"])) is None  # 平假名在 CJK 统一表意区间之外


def test_noise_empty_or_blank_facts_not_noise():
    """无有效事实 → 不判噪声（由事实数门槛兜底）；空串/None 事实被 _facts_of 忽略。"""
    assert rag._is_noise_entity(_person("阿随", "other", [])) is None
    assert rag._is_noise_entity(_person("阿随", "other", ["", None])) is None


def test_noise_real_interaction_verbs_not_matched():
    """真实互动动词（借出/邀请/帮忙/告知/探望）→ 非噪声。"""
    assert rag._is_noise_entity(_person("老王", "other",
        ["老王 lent me money.", "老王 invited me to dinner."])) is None
    assert rag._is_noise_entity(_person("张婶", "other",
        ["张婶 helped me move.", "张婶 told me the news."])) is None
    assert rag._is_noise_entity(_person("表哥", "other",
        ["表哥 informed me of the result.", "表哥 visited me in hospital."])) is None


def test_noise_conversation_partner_known_tradeoff():
    """已知权衡（当前语义）：「与TA谈论X」句式的事实同样命中谈论模式。

    若某真人的全部图谱事实均为谈话句式（无其他互动事实），会被误判 mention_only——
    这是为拦截纯被谈论名人而接受的代价；混合事实的真人不受影响
    （见 test_mixed_facts_person_kept）。此用例钉住边界，未来若改进句式解析需同步更新。
    """
    entity = _person("老李", "other", ["我和老李谈论过这件事", "又和老李谈及未来"])
    assert rag._is_noise_entity(entity) == "mention_only"


def test_supplement_path_recovers_graph_noise_via_profile(monkeypatch):
    """图谱判定噪声的实体，若被画像列为关系人 → 经 profile_only 路径恢复。

    设计语义：graph 路径的去噪启发式偏激进（all() 全命中即弃），画像（LLM 综合原文
    上下文）明确列出者视为更强信号，作为逃生通道交由用户勾选把关。
    """
    _install_graph(monkeypatch, [
        _person("雪莱", "other", [
            "The speaker discusses Shelley.",
            "A portrait of Shelley was pinned on the wall.",
        ]),
    ])
    model = _model(rels=[{"person": "雪莱", "relation": "欣赏的诗人",
                          "closeness": "distant", "influence": "精神偶像"}])
    gen = rag.RelationshipAgentGenerator()
    cands = {c["person_name"]: c for c in gen.list_candidates("g", model)}
    assert cands["雪莱"]["provenance"] == "profile_only"
    assert cands["雪莱"]["mediated_only"] is True
