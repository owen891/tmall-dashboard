"""Preview retry plan for sycm_item_flow failed units."""
import requests
import json

url = "http://127.0.0.1:5000/api/collect/runs/b3f15e208f0d4d35b32cd4cff1af864c/retry"
r = requests.post(url, json={}, timeout=30)
print("status:", r.status_code)
data = r.json()
print(json.dumps(data, ensure_ascii=False, indent=2))
