import json
from pathlib import Path

f = Path(r"E:\www\tmall-dashboard\data\collect_state.json")
data = json.loads(f.read_text(encoding="utf-8"))
data["bi_daily"] = {
    "status": "completed",
    "last_run": "2026-09-20T13:21:31",
    "error": None,
    "return_code": 0,
    "attempts": 1,
    "run_id": "ac47e901d76f44708bd047f3bff806d9",
    "output": [],
}
f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK, bi_daily reset to completed")
