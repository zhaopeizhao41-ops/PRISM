"""重跑陌生女人画像，验证待办2/3修复：source 标注 + expression_dna"""
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
        raise RuntimeError(f"{method} {path} [{e.code}]: {e.read().decode()[:400]}") from None
    if not payload.get("success", True):
        raise RuntimeError(f"{method} {path}: {json.dumps(payload, ensure_ascii=False)[:400]}")
    return payload.get("data", payload)


print("重新生成画像（含新的 source 约束与长文本证据指引）…")
gen = api("POST", "/profile/model/generate", {"project_id": PID})
task_id = gen["task_id"]
start = time.time()
while time.time() - start < 600:
    t = api("GET", f"/profile/model/generate/status/{task_id}")
    if t.get("status") == "completed":
        print(f"完成 ({int(time.time()-start)}s)")
        break
    if t.get("status") in ("failed", "error"):
        raise RuntimeError(json.dumps(t, ensure_ascii=False)[:500])
    time.sleep(6)

m = api("GET", f"/profile/model/{PID}")["model"]

# 1. source 分布统计（递归收集）
sources = {}
def walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "source" and isinstance(v, str):
                sources[v] = sources.get(v, 0) + 1
            else:
                walk(v)
    elif isinstance(node, list):
        for item in node:
            walk(item)
walk(m)
print(f"\n[待办3] source 分布: {sources}")
illegal = {s: n for s, n in sources.items() if s not in ("diary", "inference")}
print(f"  非法标注（本项目只有 diary）: {illegal or '无 ✓'}")

# 2. expression_dna / decision_patterns
print(f"\n[待办2] expression_dna: {len(m.get('expression_dna') or [])} 条")
for item in (m.get("expression_dna") or [])[:5]:
    print(f"  - {item.get('feature', '')[:80]} | 例: {str(item.get('example', ''))[:50]}")
print(f"decision_patterns: {len(m.get('decision_patterns') or [])} 条")
for item in (m.get("decision_patterns") or [])[:5]:
    print(f"  - {item.get('pattern', '')[:80]}")
