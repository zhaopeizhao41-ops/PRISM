"""补测：关系人人格卡 + 带关系人的圆桌（作家R 与 儿子上桌）"""
import json
import time
import urllib.error
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = "http://127.0.0.1:5001/api"
PID = "proj_7f21363b2c92"


def api(method, path, json_body=None, timeout=300):
    data = json.dumps(json_body).encode() if json_body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} [{e.code}]: {e.read().decode()[:500]}") from None
    if not payload.get("success", True):
        raise RuntimeError(f"{method} {path}: {json.dumps(payload, ensure_ascii=False)[:500]}")
    return payload.get("data", payload)


def poll(path, task_id, label):
    start = time.time()
    while time.time() - start < 600:
        t = api("GET", f"{path}/{task_id}")
        if t.get("status") in ("completed", "success", "done"):
            print(f"  ✓ {label} ({int(time.time()-start)}s)")
            return t
        if t.get("status") in ("failed", "error"):
            raise RuntimeError(f"{label}: {json.dumps(t, ensure_ascii=False)[:500]}")
        time.sleep(5)
    raise TimeoutError(label)


# 1. 生成关系人人格卡（person_name 键）
cands = api("GET", f"/relationship/candidates/{PID}")["candidates"]
refs = [c["person_name"] for c in cands if c["person_name"] in ("这个作家", "儿子", "作家", "伯爵")]
print(f"[1] 生成人格卡: {refs}")
task = api("POST", "/relationship/generate", {"project_id": PID, "person_refs": refs})
poll("/relationship/generate/status", task["task_id"], "人格卡")

cards = api("GET", f"/relationship/{PID}").get("cards") or []
for card in cards:
    print(f"\n  ══ {card.get('person_ref')} ══")
    print(f"  立场: {str(card.get('positions'))[:150]}")
    print(f"  关心方式: {str(card.get('communication_style') or card.get('care_style'))[:100]}")
    print(f"  盲区: {str(card.get('blind_spots'))[:100]}")
    print(f"  触发器: {json.dumps(card.get('emotional_triggers') or {}, ensure_ascii=False)[:150]}")
    print(f"  冲突模式: {json.dumps(card.get('conflict_pattern') or {}, ensure_ascii=False)[:120]}")

# 2. 带关系人的圆桌（全部宇宙 + 作家）
data = api("GET", f"/evolution/list/{PID}")
sessions = [s["session_id"] for s in (data if isinstance(data, list) else data.get("sessions", []))]
person_refs = [c.get("person_ref") for c in cards if c.get("person_ref") in ("这个作家", "作家")]
topic = "如果她的人生重来一次，你会认出她吗？"
print(f"\n[2] 圆桌: {topic}（{len(sessions)} 宇宙 + {person_refs}）")
rt = api("POST", "/roundtable/open", {
    "project_id": PID, "topic": topic,
    "session_ids": sessions, "person_refs": person_refs,
}, timeout=60)
start = time.time()
while time.time() - start < 600:
    d = api("GET", f"/roundtable/{rt['dialog_id']}")
    if d.get("status") != "running":
        break
    time.sleep(8)
else:
    raise TimeoutError("圆桌超时")

for sp in d.get("transcript") or []:
    print(f"\n  ── {sp.get('speaker_label', '?')} ──")
    print(f"  {(sp.get('content') or '').replace(chr(10), ' ')[:500]}")
mod = d.get("moderation") or {}
print(f"\n  ── 主持人 ──\n  {mod.get('summary', '')}")
