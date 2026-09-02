"""
鲁迅《孔乙己》全项目 E2E 真实管线测试
流程：
1. 创建项目（结构化量化表单 + 《孔乙己》原著全文材料）
2. 构建个人知识图谱（Zep Cloud GraphRAG + 个人固定本体）
3. 三阶段个人画像合成（Versioned Model + Hash Stamped）
4. 关系人智能体生成（咸亨酒店掌柜、丁举人、小伙计）
5. 5大原型人生分支规划（进取/平衡/保守/迂回/退出）
6. 多平行宇宙深度推演（逐阶段状态机 + 真实感账本约束 + 分叉裁决）
7. 平行宇宙圆桌辩论与主持人交叉审计报告
用法: python backend/scripts/e2e_kongyiji.py
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 设置标准输出为 UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = "http://127.0.0.1:5001/api"
TEXT_FILE = Path(__file__).parent / "kongyiji_text.txt"
KONG_TEXT = TEXT_FILE.read_text(encoding="utf-8")

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

ADVANCES = 2          # 每个宇宙推演 2 个阶段
BRANCH_COUNT = 3      # 推演前 3 个分支


def api(method, path, *, json_body=None, form=None, timeout=300):
    url = BASE + path
    if form is not None:
        boundary = "----prismE2EBoundary"
        parts = []
        for key, value in form.items():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n"
            )
        body = ("".join(parts) + f"--{boundary}--\r\n").encode("utf-8")
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
    else:
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    try:
        with _opener.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"{method} {path} 失败 [{e.code}]: {body}") from None
    if not payload.get("success", True):
        raise RuntimeError(f"{method} {path} 失败: {json.dumps(payload, ensure_ascii=False)[:800]}")
    return payload.get("data", payload)


def poll(path, task_id, interval=5, timeout=1200, label=""):
    """轮询异步任务直到完成"""
    start = time.time()
    while time.time() - start < timeout:
        task = api("GET", f"{path}/{task_id}")
        status = task.get("status")
        if status in ("completed", "success", "done"):
            print(f"  [OK] {label} 完成 ({int(time.time()-start)}s)")
            return task
        if status in ("failed", "error"):
            raise RuntimeError(f"{label} 失败: {json.dumps(task, ensure_ascii=False)[:800]}")
        print(f"  ... {label}: {task.get('message', status)} ({task.get('progress', '?')}%)")
        time.sleep(interval)
    raise TimeoutError(f"{label} 超时")


def wait_roundtable(dialog_id, interval=8, timeout=600):
    start = time.time()
    last = 0
    while time.time() - start < timeout:
        d = api("GET", f"/roundtable/{dialog_id}")
        if d.get("status") != "running":
            print(f"  [OK] 圆桌辩论完成 ({int(time.time()-start)}s)")
            return d
        n = len(d.get("transcript") or [])
        if n > last:
            last = n
            print(f"  ... 辩论发言已有 {n} 条")
        time.sleep(interval)
    raise TimeoutError("圆桌超时")


def _advance_once(session_id, project_id):
    """单次 advance，带客户端重试"""
    for attempt in range(3):
        try:
            return api("POST", f"/evolution/{session_id}/advance",
                       json_body={"project_id": project_id})
        except RuntimeError as e:
            msg = str(e)
            if attempt < 2 and ("invalid JSON" in msg or "[5" in msg):
                print(f"    推进失败，{10 * (attempt + 1)}s 后重试: {msg[:120]}")
                time.sleep(10 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def advance_with_forks(session_id, project_id):
    """推进阶段；遇到分叉默认选 option 0"""
    result = _advance_once(session_id, project_id)
    guard = 0
    while result.get("fork_required") and guard < 4:
        fork = result["fork"]
        print(f"    分叉抉择: {fork.get('question', '')[:60]}")
        for i, opt in enumerate(fork.get("options", [])[:3]):
            print(f"      [{i}] {str(opt)[:70]}")
        session = api("POST", f"/evolution/{session_id}/fork",
                      json_body={"fork_id": fork["fork_id"], "option_index": 0})
        result = _advance_once(session_id, project_id)
        guard += 1
    return result["session"]


def main():
    t0 = time.time()
    print("=" * 60)
    print("      PRISM 全流程真实性推演测试：鲁迅《孔乙己》")
    print("=" * 60)

    # ---- 1. 创建项目与量化表单拆解 ----
    print("\n[1/7] 拆解并录入《孔乙己》个人量化表单与资料...")
    form_data = {
        "name": "孔乙己",
        "age_range": "50岁左右",
        "gender": "男",
        "location": "鲁镇",
        "industry": "落魄读书人 / 抄书",
        "current_status": "穷困潦倒 / 站着喝酒而穿长衫",
        "education": "读过书，未进学（未中秀才）",
        "financial_status": "赤贫，常欠咸亨酒店十九个钱",
        "mbti": "INFP",
        "big_five": {
            "openness": 5,
            "conscientiousness": 1,
            "extraversion": 2,
            "agreeableness": 4,
            "neuroticism": 6
        },
        "tags": ["穿长衫", "站着喝酒", "窃书不能算偷", "茴字四样写法", "多乎哉不多也", "君子固穷"],
        "skills": [
            {"name": "抄书与楷书书法", "level": "4/5"},
            {"name": "四书五经诵读与经义", "level": "3/5"},
            {"name": "体力劳动与经商算账", "level": "1/5"}
        ],
        "important_relations": [
            {
                "person": "咸亨酒店掌柜",
                "relation": "债主与酒肆商人",
                "closeness": "1/5",
                "influence": "冷酷记账催债，掌柜每次见他都提十九个钱，是孔乙己在鲁镇残存的社交见证人"
            },
            {
                "person": "丁举人",
                "relation": "地方强权乡绅",
                "closeness": "1/5",
                "influence": "因孔乙己偷书到他家，施以私刑毒打并打折孔乙己双腿，彻底剥夺其肉体行动力"
            },
            {
                "person": "酒店小伙计",
                "relation": "旁观伙计",
                "closeness": "2/5",
                "influence": "孔乙己曾教其茴字写法并分茴香豆，伙计冷眼记下他最后一次出现的惨状"
            }
        ],
        "goal_short_term": "考取功名进学中秀才，或谋得一份体面的大户账房/私塾先生差事，还清粉板十九个钱",
        "current_blocker": "科举屡试不第，无谋生能力，又被丁举人打断双腿无法行走，失去尊严与生计",
        "want_to_avoid": "脱下长衫与短衣帮为伍打苦工，承认自己是贼而非读书人"
    }

    proj = api("POST", "/profile/create", json_body=form_data)
    project_id = proj["project_id"]
    print(f"  [OK] 项目创建成功: project_id = {project_id}")

    # ---- 2. 上传参考资料（鲁迅《孔乙己》原著全文）----
    print("\n[2/7] 注入参考资料：鲁迅《孔乙己》原著全文 (2500+ 字)...")
    api("POST", "/profile/materials", form={
        "project_id": project_id,
        "text": KONG_TEXT,
        "material_type": "diary",
        "time_range": "清末鲁镇",
    })
    print(f"  [OK] 原著材料已挂载，字数: {len(KONG_TEXT)} 字")

    # ---- 3. 构建知识图谱与画像合成 ----
    print("\n[3/7] 构建个人知识图谱 (Zep GraphRAG + 个人固定本体)...")
    build = api("POST", "/profile/build", json_body={"project_id": project_id})
    if build.get("reused"):
        print(f"  [OK] 复用已有图谱: graph_id = {build.get('graph_id')}")
    else:
        poll("/profile/build/status", build["task_id"], label="图谱构建")

    print("\n[4/7] 三阶段个人画像深度合成 (Personal Model Synthesis)...")
    gen = api("POST", "/profile/model/generate", json_body={"project_id": project_id})
    poll("/profile/model/generate/status", gen["task_id"], interval=8, label="画像合成")
    model_res = api("GET", f"/profile/model/{project_id}")
    model = model_res.get("model") or {}

    core = model.get("core_profile") or {}
    print(f"  * 核心一句话定位: {core.get('one_liner')}")
    print(f"  * 核心优势: {core.get('strengths')}")
    print(f"  * 致命弱点: {core.get('vulnerabilities')}")

    # ---- 4. 关系人 Agent 生成 ----
    print("\n[5/7] 识别并生成关系人智能体 (Relationship Agents)...")
    cands = api("GET", f"/relationship/candidates/{project_id}")
    candidates = cands.get("candidates") or []
    print(f"  识别到关系人候选: {[c.get('person_name') for c in candidates]}")
    
    person_refs = []
    for c in candidates:
        name = c.get("person_name")
        if name and any(k in str(name) for k in ("掌柜", "丁举人", "伙计", "何家")):
            person_refs.append(name)
    if not person_refs and candidates:
        person_refs = [c.get("person_name") for c in candidates[:2]]

    if person_refs:
        relgen = api("POST", "/relationship/generate",
                     json_body={"project_id": project_id, "person_refs": person_refs})
        poll("/relationship/generate/status", relgen["task_id"], label="关系人人格卡生成")
        cards = api("GET", f"/relationship/{project_id}").get("cards") or []
        for card in cards:
            print(f"    - {card.get('person_ref')}: 关切={card.get('core_concern')} | 风格={str(card.get('communication_style'))[:40]}")

    # ---- 5. 人生分支生成 ----
    print("\n[6/7] 生成 5 大原型人生平行分支 (Branch Planning)...")
    b_task = api("POST", "/branch/generate", json_body={"project_id": project_id, "stage_count": 3})
    poll("/branch/generate/status", b_task["task_id"], interval=6, label="人生分支规划")
    branches_data = api("GET", f"/branch/{project_id}")
    branches = branches_data.get("branches") or []
    print(f"  [OK] 成功生成 {len(branches)} 条人生分支:")
    for b in branches:
        print(f"    [{b.get('archetype')}] 适配度 {b.get('fit_score')}: {b.get('positioning')}")
        print(f"       生死假设: {b.get('key_assumption')}")

    # ---- 6. 多宇宙深度推演 ----
    print(f"\n[7/7] 启动多平行宇宙深度推演 (推演前 {min(BRANCH_COUNT, len(branches))} 个宇宙)...")
    sessions = []
    for i, branch in enumerate(branches[:BRANCH_COUNT]):
        arch = branch.get("archetype", f"Branch {i+1}")
        pos = branch.get("positioning", "")
        print(f"\n  --- 宇宙 {i+1}: [{arch}] {pos[:40]} ---")
        sess_init = api("POST", "/evolution/create",
                        json_body={"project_id": project_id, "branch_id": branch["branch_id"]})
        session_id = sess_init["session"]["session_id"]

        for st in range(ADVANCES):
            print(f"    推进阶段 {st + 1}/{ADVANCES}...")
            sess = advance_with_forks(session_id, project_id)
            stages = sess.get("stages") or []
            if stages:
                cur_stage = stages[-1]
                print(f"    [OK] 阶段 {cur_stage.get('stage_no')} 叙事: {cur_stage.get('narrative', '')[:80]}...")
                ws = cur_stage.get("world_state") or {}
                print(f"       现实账本: 事业={ws.get('career')} | 关系={ws.get('family')} | 心理={ws.get('psyche')}")
        sessions.append(session_id)

    # ---- 7. 召开平行宇宙圆桌 ----
    print("\n" + "=" * 60)
    print("      召开平行宇宙圆桌辩论：孔乙己的终极抉择")
    print("=" * 60)
    topic = "如果人生可以重来，孔乙己是否应当脱下那件长衫？"
    print(f"议题: 「{topic}」")
    
    rt_res = api("POST", "/roundtable/open", json_body={
        "project_id": project_id,
        "topic": topic,
        "session_ids": sessions,
        "person_refs": person_refs
    })
    dialog_id = rt_res["dialog_id"]
    print(f"  圆桌已召集: dialog_id = {dialog_id}")
    final_rt = wait_roundtable(dialog_id)

    print("\n【圆桌发言选摘】:")
    for sp in final_rt.get("transcript", []):
        print(f"  > {sp.get('speaker')}: {sp.get('content')[:120]}...")

    mod = final_rt.get("moderation") or {}
    print("\n【主持人交叉审计报告】:")
    print(f"  * 议题重构 (Reframe): {mod.get('reframe')}")
    print(f"  * 核心决策变量 (Decision Variable): {mod.get('decision_variable') or [d.get('decision_variable') for d in mod.get('divergences', []) if d.get('decision_variable')]}")
    print(f"  * 独立印证收敛点 (Convergences): {[c.get('point') for c in mod.get('convergences', [])]}")

    elapsed = int(time.time() - t0)
    print("\n" + "=" * 60)
    print(f"  [OK] 孔乙己全流程推演测试全部成功！总耗时: {elapsed} 秒")
    print(f"  可在浏览器访问项目进行交互检查:")
    print(f"  http://localhost:3000/branches/{project_id}")
    print(f"  http://localhost:3000/roundtable/{project_id}?dialog={dialog_id}")
    print("=" * 60)
    return project_id, dialog_id


if __name__ == "__main__":
    main()
