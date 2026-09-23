"""Execute retry for sycm_item_flow failed units, then poll status."""
import requests
import json
import time

run_id = "b3f15e208f0d4d35b32cd4cff1af864c"
url = f"http://127.0.0.1:5000/api/collect/runs/{run_id}/retry"
r = requests.post(url, json={"execute": True}, timeout=30)
print("status:", r.status_code)
data = r.json()
print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])

child_id = (data.get("data") or {}).get("child_run_id")
print("\nchild_run_id:", child_id)

if child_id:
    # Poll child run status
    for i in range(60):
        time.sleep(5)
        rr = requests.get(f"http://127.0.0.1:5000/api/collect/runs/{child_id}", timeout=15)
        d = rr.json().get("data") or {}
        run = d.get("run") or {}
        ckpts = d.get("checkpoints") or []
        st = run.get("status")
        print(f"[{i*5}s] status={st}  checkpoints={len(ckpts)}")
        if st in ("succeeded", "failed"):
            print("\n=== final run ===")
            print(json.dumps(run, ensure_ascii=False, indent=2)[:2000])
            print("\n=== checkpoints ===")
            for c in ckpts:
                print(f"  {c.get('unit_type')}:{c.get('unit_key')}  {c.get('status')}  rows={c.get('row_count')}  err={c.get('last_error_message')}")
            break
