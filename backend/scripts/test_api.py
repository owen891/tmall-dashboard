"""
测试API直接查询
"""
import requests
import json

# Test KPI API
try:
    response = requests.get("http://localhost:8000/api/kpi?dim=weekly")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"请求失败: {e}")
    if hasattr(e, 'response'):
        print(f"响应内容: {e.response.text}")
