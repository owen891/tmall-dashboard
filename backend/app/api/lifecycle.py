from fastapi import APIRouter, Query
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/api/lifecycle", tags=["生命周期分析"])

@router.get("/stats")
async def get_lifecycle_stats():
    return {
        "new": 28,
        "growing": 45,
        "mature": 32,
        "declining": 15
    }

@router.get("/distribution")
async def get_lifecycle_distribution():
    return {
        "labels": ["1月", "2月", "3月", "4月", "5月"],
        "series": {
            "new": [15, 20, 18, 22, 28],
            "growing": [35, 38, 40, 42, 45],
            "mature": [45, 42, 38, 35, 32],
            "declining": [12, 15, 18, 16, 15]
        }
    }

@router.get("/products")
async def get_lifecycle_products(stage: Optional[str] = Query(None)):
    products = {
        "new": [
            {"id": 1, "name": "2024夏季新款连衣裙", "category": "女装", "days": 7, "sales": 156, "growth": 25.3, "status": "新品"},
            {"id": 2, "name": "纯棉印花短袖T恤", "category": "男装", "days": 12, "sales": 234, "growth": 18.7, "status": "新品"},
            {"id": 3, "name": "韩版宽松休闲裤", "category": "女装", "days": 5, "sales": 89, "growth": 32.1, "status": "新品"},
            {"id": 4, "name": "透气网面运动鞋", "category": "鞋靴", "days": 15, "sales": 312, "growth": 15.4, "status": "新品"}
        ],
        "growing": [
            {"id": 5, "name": "高腰阔腿牛仔裤", "category": "女装", "days": 35, "sales": 856, "growth": 12.5, "status": "成长中"},
            {"id": 6, "name": "百搭小白鞋", "category": "鞋靴", "days": 42, "sales": 1234, "growth": 8.3, "status": "成长中"},
            {"id": 7, "name": "简约双肩包", "category": "箱包", "days": 28, "sales": 567, "growth": 15.8, "status": "成长中"},
            {"id": 8, "name": "防晒冰袖套装", "category": "配饰", "days": 38, "sales": 987, "growth": 9.6, "status": "成长中"}
        ],
        "mature": [
            {"id": 9, "name": "经典POLO衫", "category": "男装", "days": 120, "sales": 2580, "growth": 2.1, "status": "成熟期"},
            {"id": 10, "name": "商务休闲皮鞋", "category": "鞋靴", "days": 156, "sales": 1890, "growth": -1.2, "status": "成熟期"},
            {"id": 11, "name": "纯棉四件套", "category": "家纺", "days": 98, "sales": 1560, "growth": 1.8, "status": "成熟期"},
            {"id": 12, "name": "智能手表", "category": "数码", "days": 142, "sales": 3250, "growth": 0.5, "status": "成熟期"}
        ],
        "declining": [
            {"id": 13, "name": "冬季保暖羽绒服", "category": "女装", "days": 280, "sales": 320, "growth": -15.3, "status": "衰退期"},
            {"id": 14, "name": "加绒保暖内衣", "category": "内衣", "days": 312, "sales": 180, "growth": -18.7, "status": "衰退期"},
            {"id": 15, "name": "雪地靴", "category": "鞋靴", "days": 265, "sales": 450, "growth": -12.4, "status": "衰退期"},
            {"id": 16, "name": "羊毛围巾", "category": "配饰", "days": 298, "sales": 230, "growth": -20.1, "status": "衰退期"}
        ]
    }
    
    if stage and stage in products:
        return {"products": products[stage]}
    return products
