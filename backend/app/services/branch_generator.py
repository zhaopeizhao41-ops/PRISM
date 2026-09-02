"""
人生分支生成器（方案 A：纯 LLM 两步法）
消费 personal_model.json，生成 3-5 个结构化人生发展分支。

两步法（对抗分支同质化）：
  步骤1 方向穷举：LLM 基于 personal_model 的核心张力，先从 5 个原型方向
        （进取/保守/平衡/迂回/退出）中论证选取 N 个互不重叠的方向
  步骤2 逐一展开：每个方向独立一次 LLM 调用，生成完整分支
        （定位/时间线/里程碑/风险/能力要求/适配度/关键假设）

设计文档见 docs/PERSONAL_PROFILE_DESIGN.md 第七节。
"""

import json
import time
import concurrent.futures
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('prism.branch.generator')

# 5 个方向原型（步骤1 从中选取，保证分支互不重叠）
DIRECTION_ARCHETYPES = {
    "aggressive": "进取型：在现有轨迹上加码，主动争取更大的跃迁（升职/转行/创业等）",
    "conservative": "保守型：守住现有位置，优先消除风险、补齐短板",
    "balanced": "平衡型：在事业与其他人生维度（家庭/健康/爱好）之间重新分配精力",
    "detour": "迂回型：暂缓主目标，先积累某个前置条件（学历/资本/技能/人脉）再回归",
    "exit": "退出型：离开当前赛道，切换到完全不同的领域或生活方式",
}


def _is_transient_api_error(error: Exception) -> bool:
    """判断是否为瞬时性 API 错误（与 profile_synthesizer 保持一致）"""
    message = str(error).lower()
    if "perday" in message or "per_day" in message or "daily" in message:
        return False
    status_code = getattr(error, "status_code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True
    return any(
        keyword in message
        for keyword in (
            "high demand", "overloaded", "rate limit", "temporarily unavailable",
            "connection error", "connection reset", "timeout",
        )
    )


def _chat_json_with_retry(
    llm: LLMClient,
    *,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float = 0.4,
) -> Dict[str, Any]:
    """chat_json + 瞬时错误指数退避重试（最多 4 次）"""
    delays = [5, 10, 20, 30]
    for attempt in range(len(delays) + 1):
        try:
            return llm.chat_json(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_attempts=2,
            )
        except Exception as error:
            if attempt >= len(delays) or not _is_transient_api_error(error):
                raise
            logger.warning(f"瞬时 API 错误（第 {attempt + 1} 次），{delays[attempt]} 秒后重试: {error}")
            time.sleep(delays[attempt])
    raise RuntimeError("unreachable")


SYSTEM_PROMPT = """你是一位资深的人生规划顾问与社会趋势分析师。你将收到一个人的个人画像（personal_model），需要为其生成人生发展分支推演。

铁律：
1. 一切推断必须扎根于画像中的事实（时间线、特质、目标、卡点、关系人），不要引入画像外的假设
2. 尊重画像中 want_to_avoid 的边界——任何分支不得越过用户明确不想要的东西
3. 关系人（家人/伴侣/领导）的态度是分支变量之一：不同分支下他们的反应可以不同
4. 分支之间必须真正互异：不是同一方向的五种说法，而是五条有实质差异的路径
5. 推演要诚实：给出收益也给出代价与风险，不粉饰、不贩卖焦虑
6. 只输出一个 JSON 对象，不要输出其他文字"""

STEP1_PROMPT = """基于以下个人画像，从 5 个方向原型中选取 {branch_count} 个最适合此人当前处境的方向，并为每个方向写一句定位。

方向原型：
{archetypes}

选取要求：
- 选取的 {branch_count} 个方向必须互不重叠，覆盖此人当前的核心张力
- 其中至少 1 个要直接回应画像中的 aspirations（want），至少 1 个要正视 current_blocker / conflicts
- rationale 用 1-2 句话论证为什么这个方向对这个人是现实的

输出 JSON：
{{
  "selected_directions": [
    {{
      "archetype": "aggressive|conservative|balanced|detour|exit",
      "positioning": "这个分支的一句话定位",
      "rationale": "为什么选这个方向（基于画像证据）"
    }}
  ]
}}

个人画像：

{model_json}"""

STEP2_PROMPT = """基于以下个人画像与已确定的分支方向，展开这个分支的完整推演。

分支方向：{archetype_desc}
分支定位：{positioning}
选取理由：{rationale}

推演要求：
- time_span: 这个分支合理的时间跨度（如 "1-3年"）
- narrative: 300 字以内的分支叙事——从当前状态出发，这个人会如何走到分支终点
- timeline: 按时间正序的 3-5 个阶段节点，每个节点包含 period / event / state_change
- milestones: 2-4 个关键里程碑（成就或挫折）
- risks: 2-4 个主要风险，每个带 likelihood（high/medium/low）和 mitigation（一句话应对）
- capability_gaps: 这个分支要求但此人尚不具备的能力/资源
- relationship_impacts: 画像中的关系人在此分支下受到的影响（1-3 条）
- fit_score: 0-100 的适配度打分（画像证据对此分支的支持程度）
- fit_rationale: 打分理由（必须引用画像中的具体证据）
- key_assumption: 这个分支成立的最关键假设（一句话，之后可用推演器验证）
- ending_state: 若走完此分支，此人的 ending_state（一段话）

输出 JSON：
{{
  "archetype": "{archetype}",
  "positioning": "{positioning}",
  "time_span": "",
  "narrative": "",
  "timeline": [{{"period": "", "event": "", "state_change": ""}}],
  "milestones": [{{"milestone_kind": "turning_point|achievement|setback", "summary": "", "impact": ""}}],
  "risks": [{{"risk": "", "likelihood": "high|medium|low", "mitigation": ""}}],
  "capability_gaps": [""],
  "relationship_impacts": [{{"person": "", "impact": ""}}],
  "fit_score": 0,
  "fit_rationale": "",
  "key_assumption": "",
  "ending_state": ""
}}

个人画像：

{model_json}"""


class BranchGenerator:
    """人生分支两步生成器"""

    def __init__(self, api_key: Optional[str] = None):
        self.llm = LLMClient(api_key=api_key) if api_key else LLMClient()

    def generate(
        self,
        personal_model: Dict[str, Any],
        branch_count: int = 5,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        两步法生成分支集合。

        Args:
            personal_model: 完整个人模型（PersonalModelStore.get_current 的产出）
            branch_count: 分支数（3-5）
            progress_callback: (stage, message) 回调
        """
        branch_count = max(3, min(5, int(branch_count)))

        def report(stage: str, message: str):
            logger.info(f"branch generate: {stage}: {message}")
            if progress_callback:
                progress_callback(stage, message)

        # 画像裁剪：只保留步骤2需要的分区，控制 token
        model_slim = {
            key: personal_model.get(key)
            for key in (
                "basic_info", "personality", "values", "skills", "interests",
                "timeline", "milestones", "relationships", "emotional_patterns",
                "aspirations", "current_state", "conflicts",
            )
        }
        model_json = json.dumps(model_slim, ensure_ascii=False)

        # 步骤1：方向穷举
        report("directions", f"论证 {branch_count} 个分支方向")
        archetypes_text = "\n".join(f"- {k}: {v}" for k, v in DIRECTION_ARCHETYPES.items())
        step1 = _chat_json_with_retry(
            self.llm,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": STEP1_PROMPT.format(
                    branch_count=branch_count,
                    archetypes=archetypes_text,
                    model_json=model_json,
                )},
            ],
            max_tokens=2048,
        )
        directions = step1.get("selected_directions") or []
        if not directions:
            raise ValueError("方向选取失败：LLM 未返回有效方向")
        # 裁剪到目标数量
        directions = directions[:branch_count]
        report("directions", f"已选定 {len(directions)} 个方向: "
                + ", ".join(d.get("archetype", "?") for d in directions))

        # 步骤2：并发展开
        report("expand", f"开始并发展开 {len(directions)} 个分支方向…")

        def _expand_one_direction(index_and_dir):
            idx, direction = index_and_dir
            archetype = direction.get("archetype", "")
            archetype_desc = DIRECTION_ARCHETYPES.get(archetype, archetype)
            branch = _chat_json_with_retry(
                self.llm,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": STEP2_PROMPT.format(
                        archetype=archetype,
                        archetype_desc=archetype_desc,
                        positioning=direction.get("positioning", ""),
                        rationale=direction.get("rationale", ""),
                        model_json=model_json,
                    )},
                ],
                max_tokens=3000,
            )
            # 冗余字段兜底
            branch.setdefault("archetype", archetype)
            branch.setdefault("positioning", direction.get("positioning", ""))
            branch["rationale"] = direction.get("rationale", "")
            report("expand", f"分支（{archetype}）展开完成")
            return idx, branch

        branches_with_idx = []
        max_workers = min(5, len(directions))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_expand_one_direction, item) for item in enumerate(directions)]
            for future in concurrent.futures.as_completed(futures):
                branches_with_idx.append(future.result())

        # 按原方向顺序排序
        branches_with_idx.sort(key=lambda x: x[0])
        branches = [b for _, b in branches_with_idx]

        # 汇总
        report("finalize", f"共生成 {len(branches)} 个分支")
        return {
            "branches": branches,
            "branch_count": len(branches),
            "source_model_version": personal_model.get("model_version"),
            "source_content_hash": personal_model.get("content_hash"),
        }
