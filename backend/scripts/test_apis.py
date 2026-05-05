import urllib.request
import urllib.error
import json

urls = [
    ("health", "http://localhost:8000/api/health/list"),
    ("ads", "http://localhost:8000/api/ads/summary"),
]

for name, url in urls:
    try:
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/json')
        resp = urllib.request.urlopen(req)
        print(f"✓ {name}: {resp.getcode()}")
        data = json.loads(resp.read().decode())
        print(f"  Response: {json.dumps(data, ensure_ascii=False)[:200]}...")
    except urllib.error.HTTPError as e:
        print(f"✗ {name}: HTTP {e.code}")
        error_body = e.read().decode()
        print(f"  Error: {error_body[:500]}")
    except Exception as e:
        print(f"✗ {name}: {e}")
