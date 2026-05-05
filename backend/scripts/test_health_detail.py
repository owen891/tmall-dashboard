import urllib.request
import urllib.error
import json

url = "http://localhost:8000/api/health/list"
try:
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    resp = urllib.request.urlopen(req)
    print(f"✓ health: {resp.getcode()}")
    data = json.loads(resp.read().decode())
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
except urllib.error.HTTPError as e:
    print(f"✗ health: HTTP {e.code}")
    print(f"Headers: {dict(e.headers)}")
    error_body = e.read().decode()
    print(f"Error: {error_body}")
except Exception as e:
    print(f"✗ health: {type(e).__name__}: {e}")
