#!/usr/bin/env python3
import sys
import os
from http.client import HTTPConnection
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_api():
    print("=== 测试后端API ===\n")
    
    # 测试 /health
    print("1. 测试健康检查 /health")
    try:
        conn = HTTPConnection('localhost', 8000)
        conn.request('GET', '/health')
        res = conn.getresponse()
        print(f"   Status: {res.status}")
        print(f"   Response: {res.read().decode('utf-8')}")
        conn.close()
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\n2. 测试商品列表 /api/products")
    try:
        conn = HTTPConnection('localhost', 8000)
        conn.request('GET', '/api/products')
        res = conn.getresponse()
        print(f"   Status: {res.status}")
        body = res.read().decode('utf-8')
        print(f"   Response: {body[:200]}")
        
        if res.status == 200:
            data = json.loads(body)
            print(f"   成功获取商品列表!")
        conn.close()
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n3. 测试仪表盘 /api/dashboard/summary")
    try:
        conn = HTTPConnection('localhost', 8000)
        conn.request('GET', '/api/dashboard/summary')
        res = conn.getresponse()
        print(f"   Status: {res.status}")
        body = res.read().decode('utf-8')
        print(f"   Response: {body[:200]}")
        conn.close()
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\n=== 数据库检查 ===")
    from app.core import SessionLocal
    from app.models import Product, WeeklyData
    db = SessionLocal()
    count_prod = db.query(Product).count()
    count_data = db.query(WeeklyData).count()
    db.close()
    print(f"商品数量: {count_prod}")
    print(f"周数据数量: {count_data}")

if __name__ == "__main__":
    test_api()
