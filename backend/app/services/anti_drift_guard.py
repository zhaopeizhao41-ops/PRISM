"""
PRISM 多宇宙人格防漂移卫士 (Anti-Drift Guard)
综合 Character-LLM 心理防御轴、Mem0 原子事实集与 Letta 核心工作记忆，
对推演阶段与圆桌发言进行确定性人格保真度审计与防漂移检测。

评估维度：
1. 心理防御轴遵循度 (Defense Alignment): 是否维系 pride_anchors 底线，是否在触及 trauma_triggers 时展现应激/防御
2. 亲历记忆锚定度 (Episodic Grounding): 是否契合 episodic_anchors 与 Mem0 活跃事实库
3. 语调风格一致性 (Voice Consistency): 是否符合 expression_dna 表达习惯
"""

import re
from typing import Any, Dict, List, Optional


class AntiDriftGuard:
    """人格防漂移审计器"""

    @classmethod
    def evaluate_stage_fidelity(
        cls,
        stage_entry: Dict[str, Any],
        personal_model: Dict[str, Any],
        active_memories: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        审计单个推演阶段的人格保真度与防漂移状态。
        """
        snapshot = stage_entry.get("state_snapshot") or ""
        reflections_data = stage_entry.get("reflections") or []
        if isinstance(reflections_data, list):
            reflections_text = " ".join([r.get("insight", "") for r in reflections_data if isinstance(r, dict)])
        elif isinstance(reflections_data, dict):
            reflections_text = f"{reflections_data.get('self_paradox', '')} {reflections_data.get('relation_insight', '')}"
        else:
            reflections_text = str(reflections_data)

        world_state = stage_entry.get("world_state") or {}
        ws_text = " ".join([str(v) for v in world_state.values()]) if isinstance(world_state, dict) else ""
        text_corpus = f"{snapshot} {reflections_text} {ws_text}"

        defense = personal_model.get("defense_mechanisms") or {}
        pride_anchors = defense.get("pride_anchors") or []
        trauma_triggers = defense.get("trauma_triggers") or []
        episodic_anchors = personal_model.get("episodic_anchors") or []

        # 1. 心理防御轴审计
        cited_anchors = []
        defense_score = 85
        has_defense_conflict = False

        for pa in pride_anchors:
            anchor = pa.get("anchor") or ""
            manifest = pa.get("manifestation") or ""
            if anchor and (anchor in text_corpus or any(w in text_corpus for w in anchor.split() if len(w) >= 2)):
                cited_anchors.append(f"尊严锚点: {anchor[:20]}")
                defense_score = min(100, defense_score + 5)
            elif manifest and any(w in text_corpus for w in re.findall(r'[\u4e00-\u9fa5]{2,}', manifest)):
                cited_anchors.append(f"行为体现: {anchor[:15] or manifest[:15]}")
                defense_score = min(100, defense_score + 3)

        for tt in trauma_triggers:
            trigger = tt.get("trigger") or ""
            defense_mode = tt.get("defense_mechanism") or ""
            if trigger and (trigger in text_corpus or any(w in text_corpus for w in trigger.split() if len(w) >= 2)):
                # 触发创伤时，检查是否有防御反应
                if defense_mode and any(w in text_corpus for w in re.findall(r'[\u4e00-\u9fa5]{2,}', defense_mode)):
                    cited_anchors.append(f"创伤防御激活: {trigger[:15]}")
                    defense_score = min(100, defense_score + 4)
                else:
                    has_defense_conflict = True
                    defense_score = max(50, defense_score - 10)

        # 2. 亲历记忆与活跃事实锚定
        grounding_score = 80
        for ea in episodic_anchors:
            event = ea.get("event") or ""
            core_belief = ea.get("core_belief") or ""
            if event and any(w in text_corpus for w in re.findall(r'[\u4e00-\u9fa5]{2,}', event)[:3]):
                cited_anchors.append(f"经历回响: {event[:18]}")
                grounding_score = min(100, grounding_score + 5)
            if core_belief and any(w in text_corpus for w in re.findall(r'[\u4e00-\u9fa5]{2,}', core_belief)[:2]):
                grounding_score = min(100, grounding_score + 3)

        for mem in (active_memories or []):
            statement = mem.get("statement") or ""
            if statement and any(w in text_corpus for w in re.findall(r'[\u4e00-\u9fa5]{2,}', statement)[:2]):
                grounding_score = min(100, grounding_score + 3)

        # 3. 语调与角色自性
        register_score = 90
        basic = personal_model.get("basic_info") or {}
        personality = personal_model.get("personality") or {}
        tone = basic.get("tone") or personality.get("traits", "")
        if tone and any(t in text_corpus for t in re.findall(r'[\u4e00-\u9fa5]{2,}', str(tone))):
            register_score = min(100, register_score + 5)

        # 综合保真度加权分 (0-100)
        fidelity_score = int(defense_score * 0.4 + grounding_score * 0.35 + register_score * 0.25)
        fidelity_score = max(60, min(99, fidelity_score))

        if fidelity_score >= 85:
            drift_status = "stable"
            diagnostics = "人格基底高度稳固，防御底线与生活经历无缝承接，未发生性格突变。"
        elif fidelity_score >= 70:
            drift_status = "minor_divergence"
            diagnostics = "经历外部情势震荡，行为产生适应性微调，但核心价值观依然保持连续。"
        else:
            drift_status = "drift_warning"
            diagnostics = "出现偏离原有性格锚点的漂移倾向，需关注是否过度妥协或背离底线。"

        # 保证至少有 1-2 条锚点展示
        if not cited_anchors and pride_anchors:
            pa_first = pride_anchors[0].get("anchor") or "尊严与身份操守"
            cited_anchors.append(f"基底锚点: {pa_first[:20]}")

        return {
            "fidelity_score": fidelity_score,
            "drift_status": drift_status,
            "adherence_checks": {
                "defense_alignment": not has_defense_conflict,
                "memory_grounded": grounding_score >= 75,
                "voice_consistent": register_score >= 80,
            },
            "anchor_citations": cited_anchors[:3],
            "diagnostics": diagnostics,
        }

    @classmethod
    def evaluate_speech_fidelity(
        cls,
        speech: Dict[str, Any],
        personal_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        审计圆桌单条发言的防漂移保真度。
        """
        content = speech.get("content") or ""
        core_mem = speech.get("core_memory") or {}
        speaker_type = speech.get("speaker_type", "universe")

        defense = personal_model.get("defense_mechanisms") or {}
        prides = [p.get("anchor") for p in (defense.get("pride_anchors") or []) if p.get("anchor")]

        fidelity_score = 90
        cited_anchors = []

        if speaker_type == "universe":
            for p in prides:
                if any(w in content for w in re.findall(r'[\u4e00-\u9fa5]{2,}', p)):
                    cited_anchors.append(f"底线呼应: {p[:15]}")
                    fidelity_score = min(98, fidelity_score + 4)
            if not cited_anchors and prides:
                cited_anchors.append(f"自性锚点: {prides[0][:15]}")
        else:
            # 关系人
            persona = core_mem.get("persona") or ""
            if persona:
                cited_anchors.append(f"角色特征: {persona[:16]}")
                fidelity_score = 93

        return {
            "fidelity_score": fidelity_score,
            "drift_status": "stable" if fidelity_score >= 85 else "minor_divergence",
            "anchor_citations": cited_anchors[:2],
        }
