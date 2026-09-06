"""《伤逝》补测：关系人人格卡 + 带关系人的圆桌（需先跑 e2e_shangshi.py 完成推演）"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

sys.stdout.reconfigure(encoding="utf-8")

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = "http://127.0.0.1:5001/api"
PID = "proj_e143f4bb310e"
SESSIONS = ["evo_f4fbbfa5b128", "evo_f792bc02ce51", "evo_fce5d2fb4ba0"]


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


# 1. 生成关系人人格卡（子君的父亲 + 小官太太；后者为中介事实候选，需 allow_mediated 显式确认）
refs = ["子君的父亲", "小官太太"]
print(f"[1] 生成人格卡: {refs}")
task = api("POST", "/relationship/generate",
           {"project_id": PID, "person_refs": refs, "allow_mediated": True})
poll("/relationship/generate/status", task["task_id"], "人格卡")

cards = api("GET", f"/relationship/{PID}").get("cards") or []
for card in cards:
    print(f"\n  ══ {card.get('person_ref')} ══")
    print(f"  立场: {str(card.get('positions'))[:150]}")
    print(f"  关心方式: {str(card.get('communication_style') or card.get('care_style'))[:100]}")
    print(f"  盲区: {str(card.get('blind_spots'))[:100]}")
    print(f"  触发器: {json.dumps(card.get('emotional_triggers') or {}, ensure_ascii=False)[:150]}")
    print(f"  冲突模式: {json.dumps(card.get('conflict_pattern') or {}, ensure_ascii=False)[:120]}")

# 2. 带关系人的圆桌（3 宇宙 + 关系人）
topic = "在贫穷面前说出「我不再爱你」，是诚实还是残忍？——子君之死，谁该负责？"
print(f"\n[2] 圆桌: {topic}（{len(SESSIONS)} 宇宙 + {refs}）")
rt = api("POST", "/roundtable/open", {
    "project_id": PID, "topic": topic,
    "session_ids": SESSIONS, "person_refs": refs,
}, timeout=60)
start = time.time()
last = 0
d = None
while time.time() - start < 600:
    d = api("GET", f"/roundtable/{rt['dialog_id']}")
    if d.get("status") != "running":
        print(f"  ✓ 圆桌完成 ({int(time.time()-start)}s)")
        break
    n = len(d.get("transcript") or [])
    if n > last:
        last = n
        print(f"  … 发言 {n} 条")
    time.sleep(8)
else:
    raise TimeoutError("圆桌超时")

for sp in d.get("transcript") or []:
    speaker = sp.get("speaker") or sp.get("speaker_label", "?")
    print(f"\n  ── {speaker} ──")
    print(f"  {(sp.get('content') or '').replace(chr(10), ' ')[:450]}")
mod = d.get("moderation") or {}
print(f"\n  ── 主持人 ──")
print(f"  总结: {mod.get('summary', '')}")
print(f"  分歧: {json.dumps(mod.get('divergences') or '', ensure_ascii=False)[:300]}")
