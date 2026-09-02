"""
个人画像层固定本体
非 LLM 生成的预设本体，格式与 OntologyGenerator.generate() 输出一致，
可直接传入 GraphBuilderService.set_ontology()。
设计文档见 docs/PERSONAL_PROFILE_DESIGN.md 第三节。

约束：Zep 限制最多 10 个实体类型 + 10 个边类型（见 graph_builder.MAX_ONTOLOGY_TYPES），
属性名避开 Zep 保留字（name/uuid/group_id/graph_id/created_at/summary）。
"""

from typing import Any, Dict

PERSON_ONTOLOGY: Dict[str, Any] = {
    "entity_types": [
        {
            "name": "Person",
            "description": "The profile owner and every real person related to them (family, friends, colleagues, mentors).",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Name or nickname"},
                {"name": "relation_kind", "type": "text", "description": "self / family / friend / colleague / mentor / other"},
                {"name": "role", "type": "text", "description": "Occupation or social role"},
            ],
            "examples": ["the profile owner", "my mother", "college roommate"],
        },
        {
            "name": "Trait",
            "description": "Personality traits and decision patterns: MBTI type, Big Five facets, descriptive traits, or how this person typically makes decisions.",
            "attributes": [
                {"name": "trait_kind", "type": "text", "description": "mbti / big5 / descriptive / decision"},
                {"name": "evidence", "type": "text", "description": "Where this trait or decision pattern shows up"},
            ],
            "examples": ["INTP", "high openness", "procrastinates under low deadlines", "impulsive on small decisions but stalls on big ones"],
        },
        {
            "name": "Value",
            "description": "Core values and beliefs that guide decisions.",
            "attributes": [
                {"name": "value_domain", "type": "text", "description": "career / family / money / freedom / security / recognition / life"},
                {"name": "stance", "type": "text", "description": "What the person believes in this domain"},
            ],
            "examples": ["freedom over stability", "family comes first"],
        },
        {
            "name": "Skill",
            "description": "Professional or soft skills with self-assessed proficiency.",
            "attributes": [
                {"name": "skill_domain", "type": "text", "description": "professional / soft / hobby"},
                {"name": "proficiency", "type": "text", "description": "beginner / intermediate / advanced / expert"},
            ],
            "examples": ["Python data analysis", "public speaking"],
        },
        {
            "name": "Interest",
            "description": "Hobbies and topics the person enjoys, including favorite books, films and content.",
            "attributes": [
                {"name": "interest_category", "type": "text", "description": "reading / film / sport / music / tech / other"},
                {"name": "intensity", "type": "text", "description": "casual / regular / deep"},
            ],
            "examples": ["science fiction novels", "bouldering", "psychology podcasts"],
        },
        {
            "name": "Experience",
            "description": "Any life experience segment: education, work, project, life event. Unified type, use experience_kind to distinguish.",
            "attributes": [
                {"name": "experience_kind", "type": "text", "description": "education / work / project / life"},
                {"name": "period", "type": "text", "description": "Time range, e.g. 2018-2022"},
                {"name": "outcome", "type": "text", "description": "How it ended or what it led to"},
            ],
            "examples": ["CS undergraduate 2018-2022", "first job at a startup 2022-2024"],
        },
        {
            "name": "Milestone",
            "description": "Key turning points, achievements or setbacks that changed the person's trajectory.",
            "attributes": [
                {"name": "milestone_kind", "type": "text", "description": "turning_point / achievement / setback"},
                {"name": "impact", "type": "text", "description": "What changed because of it"},
            ],
            "examples": ["failed the graduate exam", "got promoted to team lead"],
        },
        {
            "name": "Aspiration",
            "description": "Goals, wishes and unfinished business, including explicit things the person does NOT want.",
            "attributes": [
                {"name": "horizon", "type": "text", "description": "short_term / mid_term / long_term"},
                {"name": "polarity", "type": "text", "description": "want / want_to_avoid"},
                {"name": "feasibility_note", "type": "text", "description": "Constraints or conditions the person mentioned"},
            ],
            "examples": ["switch to data science within 2 years", "never work overtime-heavy jobs"],
        },
        {
            "name": "Organization",
            "description": "Schools, companies, cities and other places where experiences occurred. Fallback container type.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization, school, company or city"},
                {"name": "org_kind", "type": "text", "description": "school / company / city / community / other"},
            ],
            "examples": ["Tsinghua University", "a Hangzhou internet company", "Chengdu"],
        },
        {
            "name": "EmotionalPattern",
            "description": "Recurring emotional, psychological and expression patterns observed mainly from diaries, reflections and chat logs. Expression patterns cover how the person talks: catchphrases, sentence habits, tone shifts by context.",
            "attributes": [
                {"name": "pattern_kind", "type": "text", "description": "stress / motivation / mood / self_talk / expression"},
                {"name": "trigger", "type": "text", "description": "What usually triggers this pattern, or the scene where this expression appears"},
            ],
            "examples": ["Sunday-night anxiety before work weeks", "bursts of motivation after watching others succeed", "starts replies with 'honestly' when cornered"],
        },
    ],
    "edge_types": [
        {
            "name": "EXPERIENCED",
            "description": "A person went through an experience.",
            "source_targets": [{"source": "Person", "target": "Experience"}],
            "attributes": [],
        },
        {
            "name": "HAS_TRAIT",
            "description": "A person has a personality trait.",
            "source_targets": [{"source": "Person", "target": "Trait"}],
            "attributes": [],
        },
        {
            "name": "HOLDS_VALUE",
            "description": "A person holds a value.",
            "source_targets": [{"source": "Person", "target": "Value"}],
            "attributes": [],
        },
        {
            "name": "HAS_SKILL",
            "description": "A person has a skill.",
            "source_targets": [{"source": "Person", "target": "Skill"}],
            "attributes": [],
        },
        {
            "name": "INTERESTED_IN",
            "description": "A person is interested in something.",
            "source_targets": [{"source": "Person", "target": "Interest"}],
            "attributes": [],
        },
        {
            "name": "ASPIRES_TO",
            "description": "A person holds an aspiration (want or want_to_avoid).",
            "source_targets": [{"source": "Person", "target": "Aspiration"}],
            "attributes": [],
        },
        {
            "name": "CONNECTED_TO",
            "description": "Interpersonal relationship between two persons.",
            "source_targets": [{"source": "Person", "target": "Person"}],
            "attributes": [
                {"name": "closeness", "type": "text", "description": "close / regular / distant"},
            ],
        },
        {
            "name": "OCCURRED_AT",
            "description": "An experience happened at an organization or place.",
            "source_targets": [{"source": "Experience", "target": "Organization"}],
            "attributes": [],
        },
        {
            "name": "INVOLVED",
            "description": "A person or experience involves an organization.",
            "source_targets": [
                {"source": "Person", "target": "Organization"},
                {"source": "Experience", "target": "Organization"},
            ],
            "attributes": [],
        },
        {
            "name": "LED_TO",
            "description": "An experience or milestone caused or led to another milestone. Causal chain, key material for future branch simulation.",
            "source_targets": [
                {"source": "Experience", "target": "Milestone"},
                {"source": "Milestone", "target": "Milestone"},
            ],
            "attributes": [],
        },
    ],
    "analysis_summary": "Personal profile ontology: fixed preset, not LLM-generated.",
}


def get_person_ontology() -> Dict[str, Any]:
    """返回个人画像固定本体（返回拷贝，防止调用方意外修改常量）"""
    import copy

    return copy.deepcopy(PERSON_ONTOLOGY)
