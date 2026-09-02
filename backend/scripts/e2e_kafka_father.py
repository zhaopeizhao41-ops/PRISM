"""
卡夫卡《致父亲的信》全项目 E2E 测试（真实 LLM + Zep，产生费用，手动运行）
流程：创建项目 → 上传材料 → 建图 → 画像合成 → 关系人Agent → 生成分支
      → 3 个宇宙各自推演 → 圆桌 → 宇宙对比
用法: uv run python scripts/e2e_kafka_father.py
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE = "http://127.0.0.1:5001/api"
LETTER = (Path(__file__).parent / "kafka_father_letter.txt").read_text(encoding="utf-8")

# 强制直连，绕过系统代理（fake-IP 代理会偶发劫持 localhost 返回 502）
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STAGE_COUNT = 3
ADVANCES = 2          # 每个宇宙推进 2 个阶段（费用控制）
BRANCH_COUNT = 3


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
            print(f"  ✓ {label} 完成 ({int(time.time()-start)}s)")
            return task
        if status in ("failed", "error"):
            raise RuntimeError(f"{label} 失败: {json.dumps(task, ensure_ascii=False)[:800]}")
        print(f"  … {label}: {task.get('message', status)} ({task.get('progress', '?')}%)")
        time.sleep(interval)
    raise TimeoutError(f"{label} 超时")


def wait_roundtable(dialog_id, interval=8, timeout=600):
    start = time.time()
    last = 0
    while time.time() - start < timeout:
        d = api("GET", f"/roundtable/{dialog_id}")
        if d.get("status") != "running":
            print(f"  ✓ 圆桌完成 ({int(time.time()-start)}s)")
            return d
        n = len(d.get("transcript") or [])
        if n > last:
            last = n
            print(f"  … 发言 {n} 条")
        time.sleep(interval)
    raise TimeoutError("圆桌超时")


def _advance_once(session_id, project_id):
    """单次 advance，带客户端重试（LLM 偶发非法 JSON / 瞬时 5xx）"""
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
    """推进阶段；遇到分叉默认选 option 0（最激进/第一个选项）"""
    result = _advance_once(session_id, project_id)
    guard = 0
    while result.get("fork_required") and guard < 4:
        fork = result["fork"]
        print(f"    分叉: {fork.get('question', '')[:60]}")
        for i, opt in enumerate(fork.get("options", [])[:3]):
            print(f"      [{i}] {str(opt)[:70]}")
        session = api("POST", f"/evolution/{session_id}/fork",
                      json_body={"fork_id": fork["fork_id"], "option_index": 0})
        result = _advance_once(session_id, project_id)
        guard += 1
    return result["session"]


def main():
    t0 = time.time()

    # --resume <project_id>：复用已有项目（材料已上传），从建图开始重跑
    resume_id = None
    if len(sys.argv) == 3 and sys.argv[1] == "--resume":
        resume_id = sys.argv[2]

    if resume_id:
        project_id = resume_id
        print(f"[1/9] 复用项目 {project_id}")
    else:
        # ---- 1. 创建项目 ----
        print("[1/9] 创建项目")
        proj = api("POST", "/profile/create", json_body={"name": "卡夫卡"})
        project_id = proj["project_id"]
        print(f"  project_id = {project_id}")

        # ---- 2. 上传材料（信 = diary）----
        print("[2/9] 上传材料（致父亲的信 ×1，diary）")
        api("POST", "/profile/materials", form={
            "project_id": project_id,
            "text": LETTER,
            "material_type": "diary",
            "time_range": "1919年",
        })
        print(f"  材料字符数: {len(LETTER)}")

    # ---- 3. 建图（Zep + LLM 分块）----
    print("[3/9] 构建个人知识图谱")
    build = api("POST", "/profile/build", json_body={"project_id": project_id})
    if build.get("reused"):
        print(f"  图谱已构建（复用 graph_id={build.get('graph_id')}）")
    else:
        poll("/profile/build/status", build["task_id"], label="图谱构建")

    # ---- 4. 画像合成 ----
    model = api("GET", f"/profile/model/{project_id}").get("model") or {}
    if model.get("model_version"):
        print(f"[4/9] 画像已存在（v{model['model_version']}），跳过合成")
    else:
        print("[4/9] 人格蒸馏（三阶段合成）")
        gen = api("POST", "/profile/model/generate", json_body={"project_id": project_id})
        poll("/profile/model/generate/status", gen["task_id"], interval=8, label="画像合成")
        model = api("GET", f"/profile/model/{project_id}").get("model") or {}

    print("  画像关键分区:")
    for key in ("personality", "values", "emotional_patterns", "expression_dna", "decision_patterns", "current_state"):
        section = model.get(key)
        if isinstance(section, list) and section:
            print(f"    {key}: {len(section)} 条")
        elif isinstance(section, dict) and section:
            print(f"    {key}: {json.dumps(section, ensure_ascii=False)[:150]}")
    rels = model.get("relationships") or []
    print(f"    relationships: {[r.get('person') for r in rels if isinstance(r, dict)]}")

    # ---- 5. 关系人 Agent ----
    print("[5/9] 关系人人格卡")
    try:
        existing_cards = api("GET", f"/relationship/{project_id}").get("cards") or []
    except RuntimeError:
        existing_cards = []
    if existing_cards:
        print(f"  已有 {len(existing_cards)} 张人格卡，跳过生成")
        for card in existing_cards:
            print(f"    {card.get('person_ref')}: 表达={str(card.get('communication_style'))[:60]}…")
    else:
        cands = api("GET", f"/relationship/candidates/{project_id}")
        candidates = cands.get("candidates") or []
        print(f"  候选: {[c.get('person_name') for c in candidates]}")
        person_refs = []
        for c in candidates:
            ref = c.get("person_name")
            if ref and any(k in str(ref) for k in ("父亲", "母亲", "奥特拉", "艾丽", "妹妹")):
                person_refs.append(ref)
        person_refs = person_refs[:2]
        if person_refs:
            relgen = api("POST", "/relationship/generate",
                         json_body={"project_id": project_id, "person_refs": person_refs})
            poll("/relationship/generate/status", relgen["task_id"], label="人格卡生成")
            cards = api("GET", f"/relationship/{project_id}").get("cards") or []
            for card in cards:
                print(f"    {card.get('person_ref')}: 表达={str(card.get('communication_style'))[:60]}…")
        else:
            print("  （无可匹配候选，跳过）")

    # ---- 6. 生成分支 ----
    print("[6/9] 生成人生分支")
    branches = api("GET", f"/branch/{project_id}").get("branches") or []
    if branches:
        print(f"  已有 {len(branches)} 个分支，跳过生成")
    else:
        bg = api("POST", "/branch/generate",
                 json_body={"project_id": project_id, "branch_count": BRANCH_COUNT})
        poll("/branch/generate/status", bg["task_id"], label="分支生成")
        branches = api("GET", f"/branch/{project_id}").get("branches") or []
    for i, b in enumerate(branches):
        print(f"    [{i}] {b.get('title', '')} | {str(b.get('positioning') or b.get('description') or '')[:80]}")

    # ---- 7. 三宇宙推演 ----
    print(f"[7/9] {len(branches)} 个宇宙各自推演（各 {ADVANCES} 阶段）")
    existing_sessions = api("GET", f"/evolution/list/{project_id}")
    by_archetype = {s.get("source_branch_archetype"): s for s in existing_sessions}
    sessions = []
    for i in range(min(len(branches), BRANCH_COUNT)):
        branch = branches[i]
        archetype = branch.get("archetype")
        prior = by_archetype.get(archetype)
        if prior and prior.get("status") == "active":
            s = api("GET", f"/evolution/{prior['session_id']}")
            print(f"  宇宙{i+1}「{branch.get('title', '')}」 复用 session={s['session_id'][:16]}…（已推进 {s.get('stages_done', len(s.get('stage_history') or []))} 阶段）")
        else:
            s = api("POST", "/evolution/create", json_body={
                "project_id": project_id, "branch_index": i, "stage_count": STAGE_COUNT,
            })
            print(f"  宇宙{i+1}「{branch.get('title', '')}」 session={s['session_id'][:16]}…")
        sessions.append(s)
        done = len(s.get("stage_history") or [])
        for adv in range(ADVANCES - done):
            s = advance_with_forks(s["session_id"], project_id)
            stage = (s.get("stage_history") or [{}])[-1]
            snap = stage.get("state_snapshot", "")
            print(f"    阶段{len(s.get('stage_history') or [])} [{stage.get('stage_label', '')}]: {snap[:120]}")

    # ---- 8. 圆桌 ----
    print("[8/9] 圆桌：不同人生的卡夫卡们")
    topic = "下一阶段的人生，我该继续留在布拉格和家庭里，还是彻底离开、只为自己写作而活？"
    rt = api("POST", "/roundtable/open", json_body={
        "project_id": project_id,
        "topic": topic,
        "session_ids": [s["session_id"] for s in sessions],
    }, timeout=60)
    dialog_id = rt["dialog_id"]
    dialog = wait_roundtable(dialog_id)
    print(f"  议题: {topic}")
    for speech in dialog.get("transcript") or []:
        speaker = speech.get("speaker_label") or speech.get("speaker", "?")
        content = (speech.get("content") or "").replace("\n", " ")
        print(f"\n  ── {speaker} ──")
        print(f"  {content[:400]}{'…' if len(content) > 400 else ''}")
    mod = dialog.get("moderation") or {}
    print(f"\n  ── 主持人 ──")
    print(f"  总结: {mod.get('summary', '')}")
    print(f"  分歧: {json.dumps(mod.get('divergences') or mod.get('disagreements') or '', ensure_ascii=False)[:300]}")

    # ---- 9. 宇宙对比 ----
    print("\n[9/9] 宇宙对比")
    cmp_data = api("GET", f"/evolution/compare/{project_id}")
    universes = cmp_data if isinstance(cmp_data, list) else (cmp_data.get("universes") or [])
    for u in universes:
        ws = u.get("final_world_state") or {}
        print(f"  宇宙[{u.get('archetype', '')}] 推进{u.get('stages_done', 0)}/{u.get('stage_count', '?')}阶段: "
              f"{str(u.get('final_snapshot') or '')[:150]}")
        if ws:
            print(f"    终态: career={str(ws.get('career'))[:60]} | resources={str(ws.get('resources'))[:60]}")

    print(f"\n=== E2E 完成，总耗时 {int(time.time()-t0)}s | project_id={project_id} ===")
    print(f"前端查看: http://localhost:3000 项目「卡夫卡」")


if __name__ == "__main__":
    main()
