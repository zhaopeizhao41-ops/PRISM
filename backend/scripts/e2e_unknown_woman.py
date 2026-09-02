"""
《一个陌生女人的来信》全项目 E2E 测试（真实 LLM + Zep，产生费用，手动运行）
流程：创建项目 → 上传材料 → 建图 → 画像合成 → 关系人Agent → 生成分支
      → 3 个宇宙各自推演 → 圆桌 → 宇宙对比
用法: uv run python scripts/e2e_unknown_woman.py
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE = "http://127.0.0.1:5001/api"
LETTER = (Path(__file__).parent / "unknown_woman_letter.txt").read_text(encoding="utf-8")

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


def poll(path, task_id, interval=5, timeout=900, label=""):
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


def advance_with_forks(session_id, project_id):
    """推进阶段；遇到分叉默认选 option 0（最激进/第一个选项）"""
    result = api("POST", f"/evolution/{session_id}/advance",
                 json_body={"project_id": project_id})
    guard = 0
    while result.get("fork_required") and guard < 4:
        fork = result["fork"]
        print(f"    分叉: {fork.get('question', '')[:60]}")
        for i, opt in enumerate(fork.get("options", [])[:3]):
            print(f"      [{i}] {str(opt)[:70]}")
        session = api("POST", f"/evolution/{session_id}/fork",
                      json_body={"fork_id": fork["fork_id"], "option_index": 0})
        result = api("POST", f"/evolution/{session_id}/advance",
                     json_body={"project_id": project_id})
        guard += 1
    return result["session"]


def main():
    t0 = time.time()

    # ---- 1. 创建项目 ----
    print("[1/9] 创建项目")
    proj = api("POST", "/profile/create", json_body={"name": "陌生女人"})
    project_id = proj["project_id"]
    print(f"  project_id = {project_id}")

    # ---- 2. 上传材料（信 = diary）----
    print("[2/9] 上传材料（临终来信 ×1，diary）")
    api("POST", "/profile/materials", form={
        "project_id": project_id,
        "text": LETTER,
        "material_type": "diary",
        "time_range": "临终",
    })
    print(f"  材料字符数: {len(LETTER)}")

    # ---- 3. 建图（Zep + LLM 分块）----
    print("[3/9] 构建个人知识图谱")
    build = api("POST", "/profile/build", json_body={"project_id": project_id})
    poll("/profile/build/status", build["task_id"], label="图谱构建")

    # ---- 4. 画像合成 ----
    print("[4/9] 人格蒸馏（三阶段合成）")
    gen = api("POST", "/profile/model/generate", json_body={"project_id": project_id})
    poll("/profile/model/generate/status", gen["task_id"], interval=8, label="画像合成")

    model = api("GET", f"/profile/model/{project_id}")
    print("  画像关键分区:")
    for key in ("personality", "values", "emotional_patterns", "expression_dna", "decision_patterns", "current_state"):
        section = model.get(key)
        if isinstance(section, list) and section:
            print(f"    {key}: {len(section)} 条")
        elif isinstance(section, dict) and section:
            print(f"    {key}: {json.dumps(section, ensure_ascii=False)[:150]}")
    rels = model.get("relationships") or []
    print(f"    relationships: {[r.get('name') for r in rels if isinstance(r, dict)]}")

    # ---- 5. 关系人 Agent ----
    print("[5/9] 关系人人格卡")
    cands = api("GET", f"/relationship/candidates/{project_id}")
    candidates = cands.get("candidates") or []
    print(f"  候选: {[c.get('person_ref') or c.get('name') for c in candidates]}")
    person_refs = []
    for c in candidates:
        ref = c.get("person_ref") or c.get("name")
        if ref and any(k in str(ref) for k in ("作家", "R", "儿子", "母亲")):
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
    bg = api("POST", "/branch/generate",
             json_body={"project_id": project_id, "branch_count": BRANCH_COUNT})
    poll("/branch/generate/status", bg["task_id"], label="分支生成")
    branches = api("GET", f"/branch/{project_id}").get("branches") or []
    for i, b in enumerate(branches):
        print(f"    [{i}] {b.get('title', '')} | {str(b.get('positioning') or b.get('description') or '')[:80]}")

    # ---- 7. 三宇宙推演 ----
    print(f"[7/9] {len(branches)} 个宇宙各自推演（各 {ADVANCES} 阶段）")
    sessions = []
    for i in range(min(len(branches), BRANCH_COUNT)):
        s = api("POST", "/evolution/create", json_body={
            "project_id": project_id, "branch_index": i, "stage_count": STAGE_COUNT,
        })
        sessions.append(s)
        print(f"  宇宙{i+1}「{branches[i].get('title', '')}」 session={s['session_id'][:16]}…")
        for adv in range(ADVANCES):
            s = advance_with_forks(s["session_id"], project_id)
            stage = (s.get("stage_history") or [{}])[-1]
            snap = stage.get("state_snapshot", "")
            print(f"    阶段{len(s.get('stage_history') or [])} [{stage.get('stage_label', '')}]: {snap[:120]}")

    # ---- 8. 圆桌 ----
    print("[8/9] 圆桌：不同人生的女人们")
    topic = "下一段人生，我该继续为爱而活，还是为自己而活？"
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
    for u in (cmp_data.get("universes") or []):
        print(f"  宇宙「{u.get('label', '')}」深度{u.get('depth', 0)}: "
              f"{str(u.get('latest_snapshot') or u.get('state_snapshot') or '')[:150]}")

    print(f"\n=== E2E 完成，总耗时 {int(time.time()-t0)}s | project_id={project_id} ===")
    print(f"前端查看: http://localhost:3000 项目「陌生女人」")


if __name__ == "__main__":
    main()
