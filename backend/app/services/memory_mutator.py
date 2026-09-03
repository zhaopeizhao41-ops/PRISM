"""
原子化记忆状态变更流水线（Mem0 架构）
提供 ADD / UPDATE / DELETE / NOOP 四态事实演进流水线：
- ADD: 新增独立事实/经历
- UPDATE: 状态演进/修正旧事实（如还清债务、职务变更）
- DELETE: 彻底作废或推翻的陈旧假设
- NOOP: 重复/冗余信息自动过滤，零 Token 膨胀

用于人生分支推演（EvolutionSession）与长期交互记忆管理，
确保推演在 5-10 阶段长链中保持事实一致性且 Token 消耗严格有界（O(1) 活跃记忆集）。
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from ..utils.logger import get_logger

logger = get_logger('prism.services.memory_mutator')

# 活跃记忆上限（防止长链推演中提示词无限膨胀）
MAX_ACTIVE_MEMORIES = 12

ALLOWED_ACTIONS = {"ADD", "UPDATE", "DELETE", "NOOP"}
ALLOWED_CATEGORIES = {"identity", "resource", "relation", "belief", "milestone"}


class AtomicMemoryMutator:
    """Mem0 风格原子化事实状态变更引擎"""

    @classmethod
    def init_session_memories(
        cls,
        personal_model: Dict[str, Any],
        branch: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        从个人画像与分支定位中抽取 4-6 条初始原子记忆作为推演起点。
        """
        memories: List[Dict[str, Any]] = []
        
        # 1. 身份与起点
        basic = personal_model.get("basic_info") or {}
        nickname = basic.get("nickname") or "主角"
        current_status = basic.get("current_status") or basic.get("industry") or ""
        if current_status:
            memories.append({
                "id": "mem_0_init_1",
                "subject": nickname,
                "category": "identity",
                "fact": f"{nickname}当前处于「{current_status}」状态，定位为「{branch.get('positioning', '')}」",
                "status": "active",
                "source_stage": 0,
            })
            
        # 2. 核心张力与自尊底线
        defense = personal_model.get("defense_mechanisms") or {}
        pride_list = defense.get("pride_anchors") or []
        if pride_list:
            p0 = pride_list[0]
            anchor = p0.get("anchor") or ""
            if anchor:
                memories.append({
                    "id": "mem_0_init_2",
                    "subject": nickname,
                    "category": "belief",
                    "fact": f"自尊底线：{anchor}",
                    "status": "active",
                    "source_stage": 0,
                })
                
        # 3. 初始资源/困境
        raw_aspirations = personal_model.get("aspirations") or personal_model.get("goals") or []
        wants = []
        if isinstance(raw_aspirations, list):
            for a in raw_aspirations:
                if isinstance(a, dict):
                    if a.get("polarity") == "want":
                        wants.append(a.get("content", ""))
                elif isinstance(a, str):
                    wants.append(a)
        elif isinstance(raw_aspirations, str):
            wants.append(raw_aspirations)
        wants = [w for w in wants if w]
        if wants:
            memories.append({
                "id": "mem_0_init_3",
                "subject": nickname,
                "category": "resource",
                "fact": f"当前诉求：{wants[0]}",
                "status": "active",
                "source_stage": 0,
            })
            
        # 4. 关键关系人锚点
        rels = personal_model.get("relationships") or []
        if rels:
            r0 = rels[0]
            pname = r0.get("person") or ""
            rel = r0.get("relation") or ""
            inf = r0.get("influence") or ""
            if pname:
                memories.append({
                    "id": "mem_0_init_4",
                    "subject": pname,
                    "category": "relation",
                    "fact": f"与{pname}的关系为{rel}（{inf}）" if inf else f"与{pname}的关系为{rel}",
                    "status": "active",
                    "source_stage": 0,
                })

        logger.info(f"初始化推演原子记忆: count={len(memories)}")
        return memories

    @classmethod
    def apply_mutations(
        cls,
        active_memories: List[Dict[str, Any]],
        raw_mutations: List[Dict[str, Any]],
        stage_index: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        确定性应用 Mem0 变更矩阵：
        - ADD: 生成新 ID 并追加到 active 列表
        - UPDATE: 找到 target_id 对应的记忆，将其状态置为 superseded，并将新事实并入
        - DELETE: 找到 target_id 对应的记忆，将其从 active 列表移除
        - NOOP: 仅计入变更日志，不修改 active 列表

        Returns:
            (updated_active_memories, validated_mutation_log)
        """
        active_map: Dict[str, Dict[str, Any]] = {
            m["id"]: dict(m) for m in active_memories if m.get("status", "active") == "active"
        }
        
        mutation_log: List[Dict[str, Any]] = []

        for idx, item in enumerate(raw_mutations or []):
            if not isinstance(item, dict):
                continue
            
            action = str(item.get("action", "")).upper()
            if action not in ALLOWED_ACTIONS:
                continue

            subject = str(item.get("subject", "") or "").strip()
            category = str(item.get("category", "milestone")).lower()
            if category not in ALLOWED_CATEGORIES:
                category = "milestone"
            
            fact = str(item.get("fact", "") or "").strip()
            target_id = str(item.get("target_id", "") or "").strip()
            reason = str(item.get("reason", "") or "").strip()

            if action == "NOOP":
                mutation_log.append({
                    "action": "NOOP",
                    "subject": subject or "常态",
                    "category": category,
                    "fact": fact,
                    "target_id": target_id or None,
                    "reason": reason or "与既有事实冗余，零开销忽略",
                    "stage_index": stage_index,
                })
                continue

            if action == "ADD":
                if not fact:
                    continue
                new_id = f"mem_s{stage_index}_{idx + 1}"
                new_entry = {
                    "id": new_id,
                    "subject": subject or "主角",
                    "category": category,
                    "fact": fact,
                    "status": "active",
                    "source_stage": stage_index,
                }
                active_map[new_id] = new_entry
                mutation_log.append({
                    "action": "ADD",
                    "target_id": new_id,
                    "subject": subject or "主角",
                    "category": category,
                    "fact": fact,
                    "reason": reason or "阶段新涌现原子事实",
                    "stage_index": stage_index,
                })

            elif action == "UPDATE":
                if not fact:
                    continue
                # 若 target_id 存在则更新，若不存在则模糊匹配同 subject/category 或退化为 ADD
                matched_id = target_id if target_id in active_map else None
                if not matched_id and subject:
                    # 模糊寻找同 subject 且同 category 的项
                    for mid, m in active_map.items():
                        if m.get("subject") == subject and m.get("category") == category:
                            matched_id = mid
                            break

                if matched_id and matched_id in active_map:
                    prev_fact = active_map[matched_id].get("fact", "")
                    active_map[matched_id]["fact"] = fact
                    active_map[matched_id]["source_stage"] = stage_index
                    if subject:
                        active_map[matched_id]["subject"] = subject
                    mutation_log.append({
                        "action": "UPDATE",
                        "target_id": matched_id,
                        "subject": subject or active_map[matched_id].get("subject", ""),
                        "category": category,
                        "previous_fact": prev_fact,
                        "fact": fact,
                        "reason": reason or "事实状态演进",
                        "stage_index": stage_index,
                    })
                else:
                    # 退化为 ADD
                    new_id = f"mem_s{stage_index}_{idx + 1}"
                    active_map[new_id] = {
                        "id": new_id,
                        "subject": subject or "主角",
                        "category": category,
                        "fact": fact,
                        "status": "active",
                        "source_stage": stage_index,
                    }
                    mutation_log.append({
                        "action": "ADD",
                        "target_id": new_id,
                        "subject": subject or "主角",
                        "category": category,
                        "fact": fact,
                        "reason": f"(未找到原始记录，转为新增) {reason}".strip(),
                        "stage_index": stage_index,
                    })

            elif action == "DELETE":
                matched_id = target_id if target_id in active_map else None
                if not matched_id and subject:
                    for mid, m in active_map.items():
                        if m.get("subject") == subject and m.get("category") == category:
                            matched_id = mid
                            break
                if matched_id and matched_id in active_map:
                    deleted_fact = active_map[matched_id].get("fact", "")
                    del active_map[matched_id]
                    mutation_log.append({
                        "action": "DELETE",
                        "target_id": matched_id,
                        "subject": subject or "主角",
                        "category": category,
                        "fact": deleted_fact,
                        "reason": reason or "陈旧事实作废",
                        "stage_index": stage_index,
                    })

        # 转换为列表并按上限裁剪（保留最新变更的记忆）
        updated_list = list(active_map.values())
        if len(updated_list) > MAX_ACTIVE_MEMORIES:
            # 优先保留高阶信念与最新阶段变更
            updated_list.sort(key=lambda m: (m.get("category") == "belief", m.get("source_stage", 0)), reverse=True)
            updated_list = updated_list[:MAX_ACTIVE_MEMORIES]

        logger.info(
            f"应用 Mem0 记忆变更: stage={stage_index}, "
            f"mutations={len(mutation_log)}, active_after={len(updated_list)}"
        )
        return updated_list, mutation_log

    @classmethod
    def format_active_memories_block(cls, active_memories: List[Dict[str, Any]]) -> str:
        """格式化活跃记忆集供推演 Prompt 注入（紧凑无冗余）"""
        if not active_memories:
            return "当前无活跃原子记忆。"
        
        lines = ["【当前平行宇宙活跃事实状态（Mem0 原子记忆库）】："]
        for m in active_memories:
            mid = m.get("id", "")
            cat = m.get("category", "")
            subj = m.get("subject", "")
            fact = m.get("fact", "")
            lines.append(f"- [{mid}] ({cat}·{subj}) {fact}")
        return "\n".join(lines)
