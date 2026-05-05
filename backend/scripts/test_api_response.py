"""
测试API返回的数据结构
"""
import urllib.request
import json

urls = [
    ("KPI Summary", "http://localhost:8000/api/kpi/summary?dimension=weekly"),
    ("KPI", "http://localhost:8000/api/kpi?dim=weekly"),
    ("Top Products", "http://localhost:8000/api/products/top?dim=weekly&limit=5"),
]

for name, url in urls:
    print(f"\n{'=' * 70}")
    print(f"{name}: {url}")
    print(f"{'=' * 70}")
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode('utf-8'))
        print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
        print("\n... (truncated)")
    except Exception as e:
        print(f"Error: {e}")
