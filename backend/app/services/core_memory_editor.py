"""
Letta (原 MemGPT) 风格分层核心工作记忆管理器 (Core Working Memory)
实现三层记忆结构中的第一层：In-Context Core Memory Blocks 与自主编辑流水线。

包含 3 个核心记忆块：
1. PERSONA: 角色自性、说话腔调与心理防御底线（由 Step 1 人格蒸馏初始化）
2. HUMAN: 他者心智模型（对在场各宇宙自我、重要关系人的动态认知与信任度）
3. SITUATION: 局势研判、核心矛盾与对议题的即时策略诉求

具备严格字符上限（每个 Block ≤ 250 字符），保证推演/圆桌多轮对话中 Token 消耗恒定 O(1)。
"""

from typing import Any, Dict, List, Optional, Tuple
from ..utils.logger import get_logger

logger = get_logger('prism.services.core_memory')

BLOCK_MAX_CHARS = 250
VALID_BLOCKS = {"persona", "human", "situation"}
VALID_ACTIONS = {"replace", "append", "set"}


class LettaCoreMemoryManager:
    """Letta / MemGPT 核心工作记忆管理器"""

    @classmethod
    def init_universe_core_memory(
        cls,
        session: Dict[str, Any],
        personal_model: Dict[str, Any],
    ) -> Dict[str, str]:
        """为宇宙自我 Agent 初始化 3 块 Core Memory"""
        basic = personal_model.get("basic_info") or {}
        nickname = basic.get("nickname") or "主角"
        
        # 1. PERSONA BLOCK: 自性与底线
        defense = personal_model.get("defense_mechanisms") or {}
        prides = [p.get("anchor") for p in (defense.get("pride_anchors") or []) if p.get("anchor")]
        pride_str = f"底线：{prides[0]}" if prides else "维持尊严"
        persona_content = f"{nickname}，读书人身份意识强。说话喜用文言字眼。{pride_str}。"[:BLOCK_MAX_CHARS]

        # 2. HUMAN BLOCK: 他者认知
        rels = personal_model.get("relationships") or []
        rel_snippets = []
        for r in rels[:2]:
            pname = r.get("person") or ""
            inf = r.get("influence") or r.get("relation") or ""
            if pname:
                rel_snippets.append(f"{pname}({inf})")
        human_content = f"对在场关系人认知：{'; '.join(rel_snippets)}。对其他宇宙的我持审视态度。"[:BLOCK_MAX_CHARS]

        # 3. SITUATION BLOCK: 局势与诉求
        pos = session.get("source_branch_positioning", "")
        stages_done = len(session.get("stage_history") or [])
        stage_total = len(session.get("stage_plan") or [])
        situation_content = f"宇宙定位「{pos}」，已走过{stages_done}/{stage_total}阶段。核心诉求：用本宇宙真实代价检验议题。"[:BLOCK_MAX_CHARS]

        return {
            "persona": persona_content,
            "human": human_content,
            "situation": situation_content,
        }

    @classmethod
    def init_related_core_memory(
        cls,
        card: Dict[str, Any],
        personal_model: Dict[str, Any],
    ) -> Dict[str, str]:
        """为关系人 Agent 初始化 3 块 Core Memory"""
        person = card.get("person_ref") or "关系人"
        persona_raw = card.get("persona") or ""
        comm = card.get("communication_style") or ""
        
        # 1. PERSONA BLOCK
        persona_content = f"我是{person}。{persona_raw[:100]}。说话风格：{comm[:60]}。"[:BLOCK_MAX_CHARS]

        # 2. HUMAN BLOCK: 对主角的认知
        concern = card.get("core_concern") or ""
        human_content = f"对TA的核心关切：{concern[:100]}。看重现实生计，不轻信虚言。"[:BLOCK_MAX_CHARS]

        # 3. SITUATION BLOCK
        situation_content = f"受邀参加圆桌，听到TA的多个平行可能。立场：坚守自身利益与对TA的真实期望。"[:BLOCK_MAX_CHARS]

        return {
            "persona": persona_content,
            "human": human_content,
            "situation": situation_content,
        }

    @classmethod
    def format_core_memory_block(cls, core_memory: Dict[str, str]) -> str:
        """格式化为注入提示词的紧凑文本"""
        p = (core_memory.get("persona") or "").strip()
        h = (core_memory.get("human") or "").strip()
        s = (core_memory.get("situation") or "").strip()
        return (
            "【Letta 核心工作记忆 (Core Working Memory)】\n"
            f"- [PERSONA / 角色自性]: {p}\n"
            f"- [HUMAN / 他者心智模型]: {h}\n"
            f"- [SITUATION / 局势与策略诉求]: {s}"
        )

    @classmethod
    def apply_self_edits(
        cls,
        core_memory: Dict[str, str],
        edits: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        确定性执行自编辑指令 (append / replace / set)，并进行字符截断与日志记录。
        """
        updated = dict(core_memory)
        valid_edits: List[Dict[str, Any]] = []

        for item in edits or []:
            if not isinstance(item, dict):
                continue
            block = str(item.get("block", "")).lower()
            action = str(item.get("action", "")).lower()
            content = str(item.get("content", "")).strip()
            target = str(item.get("target", "")).strip()

            if block not in VALID_BLOCKS or action not in VALID_ACTIONS or not content:
                continue

            current_val = updated.get(block, "")

            if action == "append":
                if current_val and not current_val.endswith("。") and not current_val.endswith(";"):
                    current_val += "；"
                new_val = (current_val + content)[:BLOCK_MAX_CHARS]
                updated[block] = new_val
                valid_edits.append({
                    "block": block,
                    "action": "append",
                    "content": content,
                })

            elif action == "replace":
                if target and target in current_val:
                    new_val = current_val.replace(target, content)[:BLOCK_MAX_CHARS]
                else:
                    # 未找到 target 则退化为 append
                    new_val = (current_val + f"；{content}")[:BLOCK_MAX_CHARS]
                updated[block] = new_val
                valid_edits.append({
                    "block": block,
                    "action": "replace",
                    "target": target,
                    "content": content,
                })

            elif action == "set":
                new_val = content[:BLOCK_MAX_CHARS]
                updated[block] = new_val
                valid_edits.append({
                    "block": block,
                    "action": "set",
                    "content": content,
                })

        return updated, valid_edits
