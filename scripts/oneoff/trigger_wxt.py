"""Trigger wanxiangtai collection via API and poll until done."""
import requests
import json
import time

BASE = "http://127.0.0.1:5000"

# Trigger
r = requests.post(f"{BASE}/api/collect/trigger", json={"source": "wanxiangtai"}, timeout=15)
print("trigger status:", r.status_code)
data = r.json()
print(json.dumps(data, ensure_ascii=False, indent=2)[:800])

run_id = (data.get("data") or {}).get("run_id")
print("\nrun_id:", run_id)

if not run_id:
    raise SystemExit("no run_id")

# Poll run
for i in range(120):
    time.sleep(5)
    try:
        rr = requests.get(f"{BASE}/api/collect/runs/{run_id}", timeout=15)
        rd = rr.json().get("data") or {}
        run = rd.get("run") or {}
        ckpts = rd.get("checkpoints") or []
        st = run.get("status")
        n_succ = sum(1 for c in ckpts if c.get("status") == "succeeded")
        n_fail = sum(1 for c in ckpts if c.get("status") == "failed")
        print(f"[{i*5}s] status={st}  ckpts={len(ckpts)} (succ={n_succ}, fail={n_fail})")
        if st in ("succeeded", "failed"):
            print("\n=== final run ===")
            print("status:", run.get("status"))
            print("error_code:", run.get("error_code"))
            print("error_message:", (run.get("error_message") or "")[-500:])
            print("stats:", run.get("stats_json"))
            print("\n=== checkpoints (last 20) ===")
            for c in ckpts[-20:]:
                print(f"  {c.get('unit_type')}:{c.get('unit_key')}  {c.get('status')}  rows={c.get('row_count')}  err={c.get('last_error_message')}")
            break
    except Exception as e:
        print(f"[{i*5}s] poll err: {e}")
