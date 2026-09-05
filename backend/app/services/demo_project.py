"""Seed a complete, local-only demo project for first-time users.

The demo deliberately bypasses LLM and Zep. It exercises the same persisted
stores as a real project, so every workflow page is useful before a user
uploads personal material or configures a cloud provider.
"""

import json
import os
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Tuple

from ..models.action_experiment import ActionExperimentStore
from ..models.branch import BranchStore
from ..models.evolution import EvolutionStore
from ..models.personal_model import PersonalModelStore
from ..models.project import ProjectManager, ProjectStatus
from ..models.relationship_agent import RelationshipAgentStore
from ..models.roundtable import RoundtableStore
from ..services.person_ontology import get_person_ontology
from ..services.profile_materials import build_evidence_index, material_fingerprint


DEMO_PROJECT_NAME = "PRISM 演示 · 下一步"
_demo_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _material(material_id: str, material_type: str, text: str, *, goals=None) -> Dict[str, Any]:
    return {
        "material_id": material_id,
        "material_type": material_type,
        "material_mode": "personal",
        "schema_version": 2,
        "fingerprint": material_fingerprint(text),
        "char_count": len(text),
        "preview": text[:200],
        "normalized_text": text,
        "chunks": build_evidence_index(material_id, text, chunk_size=500, overlap=50),
        "goals": goals or [],
    }


def _ref(material_id: str, ordinal: int = 0) -> Dict[str, str]:
    return {"material_id": material_id, "chunk_id": f"{material_id}:c{ordinal}"}


def _stage(
    index: int,
    label: str,
    career: str,
    family: str,
    resources: str,
    psyche: str,
    snapshot: str,
    realism: Dict[str, Any],
    events=None,
) -> Dict[str, Any]:
    return {
        "stage_index": index,
        "stage_label": label,
        "world_state": {
            "career": career,
            "family": family,
            "resources": resources,
            "psyche": psyche,
        },
        "state_snapshot": snapshot,
        "occurred_events": events or [],
        "reflections": [],
        "stakeholder_moves": [],
        "memory_mutations": [],
        "active_memories_count": 3,
        "anti_drift": {
            "fidelity_score": 91,
            "drift_status": "stable",
            "diagnostics": "关键经历与画像底座保持一致。",
            "anchor_citations": ["保持现金缓冲", "每周保留固定创作时段"],
        },
        "realism": realism,
        "divergence_note": None,
    }


def _realism(cash: int, debt: int, health: int, stress: int, tension: int) -> Dict[str, Any]:
    return {
        "health_score": health,
        "stress_carryover": stress,
        "finance": {
            "cash_months": cash,
            "debt_months": debt,
            "income_stability": 4 if cash >= 6 else 3,
            "known": True,
        },
        "relationships": [{
            "name": "林舟",
            "role": "朋友与合作者",
            "tension": tension,
            "last_event": "讨论工作节奏与合作边界",
        }],
        "life_event": None,
        "causal_violations_remaining": [],
    }


def _seed_manifest(project_id: str) -> None:
    journal = (
        "最近三个月，我一边做数据产品项目，一边维持本职工作。稳定收入让我安心，\n"
        "但每周能真正用于创作的时间很少。林舟愿意帮我验证用户需求，我希望先用小规模试验\n"
        "证明有人愿意付费，再决定是否离开当前岗位。我的底线是保留至少六个月现金缓冲，\n"
        "不把家庭关系和健康当作换取速度的成本。"
    )
    form = (
        "【基本盘】年龄段: 25-30; 所在城市: 杭州; 行业/职业方向: 数据产品; "
        "当前状态: 在职迷茫\n【目标与困扰】近1-3年最想实现的事: 做出可持续的数据产品; "
        "当前最大的卡点: 时间与现金流有限; 明确不想要的: 长期透支健康"
    )
    goals = [
        {"goal_id": "goal_1", "horizon": "short_term", "content": "做出可持续的数据产品", "polarity": "want"},
        {"goal_id": "goal_2", "horizon": "short_term", "content": "长期透支健康", "polarity": "want_to_avoid"},
    ]
    manifest = [
        _material("mat_demo_journal", "diary", journal, goals=goals),
        _material("mat_demo_form", "structured_form", form, goals=goals),
    ]
    path = os.path.join(ProjectManager._get_project_dir(project_id), "materials_manifest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"schema_version": 2, "materials": manifest}, handle, ensure_ascii=False, indent=2)
    ProjectManager.save_extracted_text(project_id, "\n\n".join(item["normalized_text"] for item in manifest))


def _seed_model(project_id: str) -> None:
    journal_ref = [_ref("mat_demo_journal")]
    form_ref = [_ref("mat_demo_form")]
    goals = [
        {"goal_id": "goal_1", "horizon": "short_term", "content": "做出可持续的数据产品", "polarity": "want"},
        {"goal_id": "goal_2", "horizon": "short_term", "content": "长期透支健康", "polarity": "want_to_avoid"},
    ]
    model = {
        "schema_version": 2,
        "model_version": 1,
        "created_at": _now(),
        "entity_count": 24,
        "basic_info": {
            "nickname": "小岚",
            "age_range": "25-30",
            "gender": None,
            "location": "杭州",
            "industry": "数据产品",
            "current_status": "在职迷茫",
            "education_level": None,
            "financial_state": "稳定有结余",
        },
        "personality": {
            "mbti": {"value": "INTJ", "confidence": "medium", "conflict_note": None, "evidence_refs": form_ref},
            "big5": {"openness": 6, "conscientiousness": 6, "extraversion": 3, "agreeableness": 4, "neuroticism": 4},
            "self_view": [{"trait": "深度思考", "source": "structured_form", "evidence_refs": form_ref}],
            "observed": [{"trait": "先小规模验证再承担大风险", "source": "diary", "evidence": "先用小规模试验验证用户需求", "evidence_refs": journal_ref}],
        },
        "values": [
            {"domain": "安全", "stance": "保留至少六个月现金缓冲", "source": "diary", "evidence_refs": journal_ref},
            {"domain": "健康", "stance": "不把健康当作换取速度的成本", "source": "diary", "evidence_refs": journal_ref},
        ],
        "skills": [
            {"name": "数据分析", "domain": "专业", "proficiency": "4/5", "source": "structured_form", "evidence_refs": form_ref},
            {"name": "用户访谈", "domain": "软技能", "proficiency": "3/5", "source": "diary", "evidence_refs": journal_ref},
        ],
        "interests": [{"category": "创作", "item": "把复杂问题做成工具", "intensity": "deep", "source": "diary", "evidence_refs": journal_ref}],
        "emotional_patterns": [{"pattern_kind": "stress", "trigger": "时间被工作切碎时容易焦虑", "source": "diary", "evidence": "每周能真正用于创作的时间很少", "evidence_refs": journal_ref}],
        "expression_dna": [{"feature": "先陈述约束再提出方案", "scene": "做决定时", "example": "先用小规模试验证明有人愿意付费", "source": "diary", "evidence_refs": journal_ref}],
        "decision_patterns": [{"pattern": "验证后再扩大投入", "style": "谨慎、重视可逆性", "evidence": "希望先用小规模试验验证用户需求", "source": "diary", "evidence_refs": journal_ref}],
        "defense_mechanisms": {
            "pride_anchors": [{"anchor": "把复杂问题做成可用产品", "evidence": "持续推进数据产品项目", "defense_behavior": "被催促时会回到指标和证据", "source": "diary", "evidence_refs": journal_ref}],
            "trauma_triggers": [{"trigger": "长期失控的加班节奏", "evidence": "不想长期透支健康", "response_pattern": "会暂停扩张并重新核算时间", "source": "diary", "evidence_refs": journal_ref}],
        },
        "timeline": [
            {"period": "过去两年", "kind": "work", "summary": "在数据产品岗位积累经验", "outcome": "形成独立项目能力", "source": "structured_form", "evidence_refs": form_ref},
            {"period": "最近三个月", "kind": "project", "summary": "下班后启动数据产品试验", "outcome": "找到首批访谈对象", "source": "diary", "evidence_refs": journal_ref},
        ],
        "milestones": [{"milestone_kind": "turning_point", "summary": "决定先验证付费意愿", "impact": "把辞职冲动转成可测的小实验", "source": "diary", "evidence_refs": journal_ref}],
        "episodic_anchors": [{"scene": "深夜整理用户访谈记录", "involved_persons": ["林舟"], "core_conflict": "想加速又担心现金流和健康", "emotional_imprint": "兴奋与焦虑并存", "cognitive_anchor": "先做可逆验证，再承担不可逆成本", "source": "diary", "evidence_refs": journal_ref}],
        "relationships": [{"person": "林舟", "relation": "朋友与合作者", "closeness": "close", "influence": "帮助验证需求，也会提醒我不要透支", "source": "diary", "evidence_refs": journal_ref}],
        "aspirations": goals,
        "conflicts": [],
        "current_state": "小岚正处在稳定工作与独立创作之间的过渡期。核心张力不是要不要改变，而是如何在保留现金与健康缓冲的前提下，获得足够真实的用户验证。",
        "open_questions": ["首批用户是否愿意付费？", "每周能稳定投入多少创作时间？", "林舟适合承担怎样的合作边界？"],
        "source_coverage": {"structured_form": 0.95, "diary": 0.72},
        "traceability": {"warnings": [], "validated_items": 14},
        "evidence_refs": journal_ref,
    }
    PersonalModelStore.save(project_id, model)


def _branch(branch_id: str, archetype: str, positioning: str, fit: int, assumption: str, ending: str, *, risk: str) -> Dict[str, Any]:
    return {
        "branch_id": branch_id,
        "archetype": archetype,
        "positioning": positioning,
        "time_span": "12-18个月",
        "narrative": f"从当前岗位出发，小岚选择{positioning}。先把目标拆成可验证的阶段，在现金、时间和关系约束内逐步推进。",
        "rationale": "画像显示其擅长先验证再扩大投入，同时重视安全与健康边界。",
        "timeline": [
            {"period": "0-3个月", "event": "完成 10 次用户访谈", "state_change": "获得真实需求证据"},
            {"period": "4-9个月", "event": "发布最小可用版本", "state_change": "从想法进入市场反馈"},
            {"period": "10-18个月", "event": "根据付费信号决定是否扩大", "state_change": "保留可逆的选择空间"},
        ],
        "milestones": [{"milestone_kind": "achievement", "summary": "拿到首批付费用户", "impact": "验证产品方向"}],
        "risks": [{"risk": risk, "likelihood": "medium", "mitigation": "每月复核现金、健康和用户反馈，必要时缩小范围"}],
        "capability_gaps": ["稳定的每周交付节奏", "定价与销售验证"],
        "relationship_impacts": [{"person": "林舟", "impact": "需要提前约定合作投入与退出边界"}],
        "fit_score": fit,
        "fit_rationale": "与‘先验证再扩大投入’和‘保留六个月缓冲’两条画像证据一致。",
        "key_assumption": assumption,
        "goal_refs": ["goal_1", "goal_2"],
        "dominant_goal_polarity": "mixed",
        "ending_state": ending,
        "source_model_version": 1,
    }


def _seed_branches(project_id: str) -> None:
    BranchStore.save(project_id, {
        "schema_version": 2,
        "source_model_version": 1,
        "branch_count": 3,
        "branches": [
            _branch("branch_demo_balanced", "balanced", "保留收入，逐步转型数据产品", 88, "产品在六个月内获得稳定付费信号", "仍有现金缓冲，同时拥有一条被市场验证过的新路径。", risk="本职与副业并行导致交付节奏被切碎"),
            _branch("branch_demo_aggressive", "aggressive", "离职后全职投入产品创业", 61, "至少有十二个月现金储备且产品很快获得付费", "获得更快的市场反馈，但现金和心理压力显著上升。", risk="收入中断后压力迫使产品做出短视选择"),
            _branch("branch_demo_conservative", "conservative", "深耕当前岗位，把产品作为长期副业", 74, "岗位仍能提供稳定成长与固定创作时段", "风险最低，但产品验证速度和转型窗口都更慢。", risk="稳定感变成拖延，错过持续验证的节奏"),
        ],
    })


def _seed_session(project_id: str, session_id: str, branch: Dict[str, Any], *, aggressive: bool = False) -> None:
    if aggressive:
        stages = [
            _stage(1, "离职试水", "全职搭建 MVP", "家人担心但保持沟通", "现金缓冲下降", "兴奋，压力上升", "离开岗位后集中完成 MVP，获得了更快的反馈。", _realism(8, 0, 84, 38, 35), ["完成首个可用版本"]),
            _stage(2, "市场验证", "开始接触付费客户", "合作边界出现摩擦", "获客支出增加", "对收入波动敏感", "访谈转化率不错，但付费周期比预期更长。", _realism(6, 1, 79, 53, 49), ["两名用户要求试用延期"]),
            _stage(3, "收缩与调整", "砍掉低价值功能", "林舟建议保留兼职收入", "现金缓冲仍可支撑", "重新获得掌控感", "小岚暂停扩张，先把产品收敛到一个清晰场景。", _realism(6, 1, 81, 46, 42), ["确定单一目标用户"]),
            _stage(4, "重新选择", "形成可持续产品节奏", "合作规则重新写清", "收入开始恢复", "谨慎乐观", "产品获得稳定小额收入，小岚保留了重新选择工作的空间。", _realism(7, 1, 83, 39, 34), ["签下首个年度客户"]),
        ]
    else:
        stages = [
            _stage(1, "小步验证", "保持岗位并完成访谈", "家人支持试验", "现金缓冲稳定", "谨慎兴奋", "小岚用固定晚间时段完成了十次访谈，没有急着辞职。", _realism(10, 0, 88, 24, 28), ["完成十次访谈"]),
            _stage(2, "最小交付", "发布 MVP 并获得反馈", "林舟加入每周复盘", "支出可控", "节奏变稳", "首批用户愿意试用，产品从想法变成了可以被检验的东西。", _realism(9, 0, 87, 26, 31), ["发布 MVP", "获得三位试用用户"]),
            _stage(3, "付费信号", "拿到首批付费订单", "合作边界被明确", "收入出现新来源", "信心增加", "小额付费证明方向有价值，小岚开始重新计算转型时间表。", _realism(9, 0, 89, 22, 25), ["首批付费订单"]),
            _stage(4, "可逆转型", "把转型变成阶段性选择", "关系保持稳定", "现金与收入双重缓冲", "踏实", "小岚没有把人生押在一次跳跃上，而是获得了更大的选择空间。", _realism(9, 0, 90, 18, 21), ["确定下一阶段投入上限"]),
        ]
    fork = {
        "fork_id": f"fork_demo_{session_id[-8:]}",
        "at_stage": 2,
        "question": "当第一批反馈到来时，是否扩大投入？",
        "options": [{"label": "先保持小规模", "condition": "现金与健康优先"}, {"label": "立即全职投入", "condition": "用速度换取市场窗口"}],
        "resolved": {"option_index": 0 if not aggressive else 1, "label": "先保持小规模" if not aggressive else "立即全职投入"},
    }
    session = {
        "schema_version": 2,
        "revision": 0,
        "session_id": session_id,
        "project_id": project_id,
        "source_branch_archetype": branch["archetype"],
        "source_branch_positioning": branch["positioning"],
        "source_branch_timeline": branch["timeline"],
        "source_branch_assumption": branch["key_assumption"],
        "source_model_version": 1,
        "protagonist": "小岚",
        "stage_plan": [{"stage_label": item["stage_label"], "focus": item["world_state"]["career"]} for item in stages],
        "stage_history": stages,
        "pending_forks": [fork],
        "user_events": [],
        "status": "completed",
        "created_at": _now(),
        "initial_state": "稳定工作与独立创作并行，正在寻找可逆的转型方式。",
        "active_memories": ["先验证再扩大投入", "保留现金与健康缓冲", "合作边界需要说清"],
        "realism_state": stages[-1]["realism"],
    }
    EvolutionStore.save(session)


def _seed_relationships(project_id: str) -> None:
    RelationshipAgentStore.save(project_id, {
        "schema_version": 2,
        "cards": [{
            "person_ref": "林舟",
            "relation_kind": "friend",
            "persona": "务实、愿意一起验证产品，但不接受长期没有边界的投入。",
            "core_concern": "希望合作有清晰分工，也不希望小岚用健康换速度。",
            "communication_style": "直接、具体，习惯先问指标和时间表。",
            "emotional_triggers": {"opens_up_when": "看到真实用户反馈", "defensive_when": "合作边界被模糊"},
            "conflict_pattern": {"style": "先暂停争论，再回到事实", "repair": "写下下一步分工"},
            "memory_signature": ["一起做过第一次用户访谈", "每周复盘产品方向"],
            "known_positions": [{"topic": "是否辞职", "stance": "先获得付费信号再决定"}],
            "blind_spots": ["不知道小岚具体的财务底线"],
            "thin": False,
        }],
    })


def _seed_roundtable(project_id: str) -> None:
    created = _now()
    RoundtableStore.save({
        "schema_version": 2,
        "revision": 0,
        "dialog_id": "rt_demo_choice",
        "project_id": project_id,
        "topic": "我应该现在离职全职做产品，还是继续用小规模试验换取确定性？",
        "total_rounds": 2,
        "status": "completed",
        "created_at": created,
        "participants": [
            {"type": "universe", "session_id": "evo_demo_balanced", "label": "平衡宇宙的我", "archetype": "balanced"},
            {"type": "universe", "session_id": "evo_demo_aggressive", "label": "进取宇宙的我", "archetype": "aggressive"},
            {"type": "related", "person_ref": "林舟", "label": "林舟", "relation_kind": "friend"},
        ],
        "transcript": [
            {"speaker": "平衡宇宙的我", "speaker_type": "universe", "round": 1, "content": "我先保留收入，不是因为害怕，而是因为我需要让用户反馈而不是焦虑替我做决定。"},
            {"speaker": "进取宇宙的我", "speaker_type": "universe", "round": 1, "content": "全职让我更快找到答案，但现金下降后每个反馈都会被放大成生存问题。速度确实有价值，代价也是真的。"},
            {"speaker": "林舟", "speaker_type": "related", "round": 1, "content": "我支持你做产品，但支持不等于替你承担没有边界的风险。先把合作和付费信号说清楚。"},
            {"speaker": "平衡宇宙的我", "speaker_type": "universe", "round": 2, "content": "真正的变量不是勇不勇敢，而是能否把验证周期缩短到现金缓冲允许的范围。"},
            {"speaker": "林舟", "speaker_type": "related", "round": 2, "content": "那就把下一步写成一个月的实验：有指标就加码，没有指标就调整，而不是用辞职证明决心。"},
        ],
        "moderation": {
            "summary": "圆桌没有替小岚做决定，但把分歧收敛到一个可验证的变量：在现金与健康底线内，能否获得足够强的付费信号。",
            "epistemic_consensus": {
                "convergence_index": 82,
                "inevitability_score": 64,
                "leverage_ratio": 78,
                "inevitable_constraints": [{"constraint": "现金缓冲决定试验窗口", "why": "两个宇宙都观察到收入波动会改变选择空间", "impact": "必须先设定投入上限"}],
                "high_leverage_variables": [{"variable": "首批用户付费信号", "mechanism": "决定是否把可逆试验升级为全职投入", "optimal_timing": "未来 30 天"}],
            },
            "audit": [
                {"verdict": "grounded", "speaker": "平衡宇宙的我", "claim": "先保留收入", "note": "与现金缓冲和小规模验证记录一致"},
                {"verdict": "grounded", "speaker": "林舟", "claim": "合作需要边界", "note": "与关系人卡片中的已知立场一致"},
            ],
            "convergences": [{"type": "hard", "confidence": "high", "point": "付费信号比情绪上的决心更能决定下一步", "supporting": ["平衡宇宙的我", "进取宇宙的我", "林舟"]}],
            "divergences": [{"root_cause": "choice", "topic": "何时把产品投入升级为全职", "positions": [{"universe": "平衡宇宙", "claim": "先保持小规模"}, {"universe": "进取宇宙", "claim": "立即全职投入"}], "root_note": "分歧来自风险承受和现金窗口，不是目标不同。", "decision_variable": "首批用户付费信号"}],
            "reframe": "把‘要不要辞职’改写为‘未来 30 天怎样获得足够强的付费证据’。",
            "open_questions": ["十次访谈中有多少人愿意付费？", "每周固定投入时段能否连续四周保持？"],
        },
    })


def _seed_action(project_id: str) -> None:
    review = (date.today() + timedelta(days=30)).isoformat()
    ActionExperimentStore.create(project_id, {
        "title": "30 天付费信号实验",
        "horizon_days": 30,
        "goal": "验证数据产品是否有明确的付费需求",
        "minimum_action": "完成 10 次目标用户访谈，并向其中 3 人展示可用原型",
        "success_metric": "至少 2 人愿意支付或签署明确试用承诺",
        "stop_condition": "连续两周没有有效访谈，或健康评分明显下降",
        "expected_cost": "每周 4 小时，少量原型制作成本",
        "review_date": review,
        "source_session_id": "evo_demo_balanced",
        "source_summary": "来自平衡宇宙与圆桌共同指出的高杠杆变量。",
    })


def ensure_demo_project() -> Tuple[Any, bool]:
    """Return the existing demo or create it once, without external calls."""
    # The endpoint is intentionally idempotent even when two first-time users
    # click the CTA at the same time in a single backend process.
    with _demo_lock:
        for project in ProjectManager.list_projects(limit=None):
            if getattr(project, "is_demo", False):
                return project, False

        project = ProjectManager.create_project(DEMO_PROJECT_NAME)
        project.project_type = "personal_profile"
        project.is_demo = True
        project.status = ProjectStatus.GRAPH_COMPLETED
        project.profile_scope = "personal"
        project.decision_context = {
            "question": "我应该现在离职全职做产品，还是继续用小规模试验换取确定性？",
            "horizon": "1_year",
            "constraints": "保留至少六个月现金缓冲，不以长期透支健康换取速度。",
        }
        project.ontology = get_person_ontology()
        project.analysis_summary = "本地脱敏演示项目：不调用 LLM 或 Zep Cloud。"
        project.privacy_settings.update({
            "cloud_processing_consent": False,
            "consent_source": "demo_local_only",
            "consent_updated_at": None,
            "retention_days": None,
            "demo_local_only": True,
        })
        ProjectManager.save_project(project)
        _seed_manifest(project.project_id)
        _seed_model(project.project_id)
        _seed_branches(project.project_id)
        _seed_session(project.project_id, "evo_demo_balanced", BranchStore.get_current(project.project_id)["branches"][0])
        _seed_session(project.project_id, "evo_demo_aggressive", BranchStore.get_current(project.project_id)["branches"][1], aggressive=True)
        _seed_relationships(project.project_id)
        _seed_roundtable(project.project_id)
        _seed_action(project.project_id)
        return ProjectManager.get_project(project.project_id), True
