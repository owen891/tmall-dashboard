#!/usr/bin/env python3
"""
Simple backend server - just for preview
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sample data
sample_products = [
    {
        "product_id": "P00001",
        "title": "精品商品1",
        "category": "家居饰品/摆件类/装饰摆件",
        "tier": "引流款"
    },
    {
        "product_id": "P00002",
        "title": "精品商品2",
        "category": "收纳整理/家庭收纳用具/收纳箱",
        "tier": "利润款"
    }
]

sample_daily_data = []
import random
from datetime import datetime, timedelta
for i in range(30):
    date = (datetime.now() - timedelta(days=30 - i)).strftime("%Y-%m-%d")
    sample_daily_data.append({
        "date": date,
        "payment_amount": random.randint(1000, 10000),
        "visitors": random.randint(100, 1000),
        "conversion": round(random.uniform(0.01, 0.05), 3),
        "ad_spend": random.randint(50, 500)
    })

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Backend API is running"}

@app.get("/api/dashboard/summary")
def dashboard_summary():
    return {
        "total_payment": 125800,
        "total_orders": 568,
        "total_visitors": 15800,
        "conversion": 0.036,
        "roi": 3.2
    }

@app.get("/api/products")
def list_products():
    return {
        "items": sample_products,
        "total": len(sample_products)
    }

@app.get("/api/trends/daily")
def get_daily_trends():
    return {
        "items": sample_daily_data,
        "total": len(sample_daily_data)
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting backend preview server...")
    print("📊 Frontend at http://localhost:5173")
    print("🔌 API at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
