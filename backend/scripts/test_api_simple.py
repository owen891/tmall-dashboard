import urllib.request
import json

try:
    url = "http://localhost:8000/api/kpi?dim=weekly"
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    data = response.read().decode('utf-8')
    print("Success!")
    print(json.dumps(json.loads(data), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
