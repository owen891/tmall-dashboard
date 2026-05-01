#!/usr/bin/env python3
import sys
import os
from http.client import HTTPConnection
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== 测试 /api/products/ (带 trailing slash) ===")

try:
    conn = HTTPConnection('localhost', 8000)
    conn.request('GET', '/api/products/')
    res = conn.getresponse()
    print(f"Status: {res.status}")
    data = json.loads(res.read().decode('utf-8'))
    print(f"数据获取成功！")
    print(f"Total: {data.get('total')}")
    print(f"Items: {len(data.get('data', []))}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试 /api/products (不带 trailing slash) ===")
try:
    conn = HTTPConnection('localhost', 8000)
    conn.request('GET', '/api/products')
    res = conn.getresponse()
    print(f"Status: {res.status}")
    print(f"Headers: {dict(res.getheaders())}")
    body = res.read().decode('utf-8')
    print(f"Body: {body[:200]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
