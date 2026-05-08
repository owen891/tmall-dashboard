from fastapi import APIRouter, Query, Depends
from sqlalchemy import func
from app.models import Product, WeeklyData, DailyData, MonthlyData
from app.core.database import get_db
from typing import Optional

router = APIRouter(prefix="/market", tags=["市场分析"])

@router.get("/category-stats")
async def get_category_stats(
    dimension: str = Query("weekly", description="时间维度"),
    db=Depends(get_db)
):
    """获取各类目统计数据"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    results = db.query(
        Product.category,
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.payment_quantity).label('quantity'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.count(Model.product_id).label('product_count')
    ).join(
        Model, Product.product_id == Model.product_id
    ).group_by(
        Product.category
    ).having(
        Product.category.isnot(None)
    ).all()

    trends = []
    for r in results:
        gmv = float(r.gmv or 0)
        quantity = int(r.quantity or 0)
        avg_price = gmv / quantity if quantity > 0 else 0
        trends.append({
            "category": r.category or "未分类",
            "gmv": round(gmv, 2),
            "quantity": quantity,
            "avg_price": round(avg_price, 2),
            "conversion": round(float(r.conversion or 0) * 100, 2),
            "product_count": r.product_count
        })

    trends.sort(key=lambda x: x['gmv'], reverse=True)
    return {"categories": [t['category'] for t in trends], "data": trends}

@router.get("/price-distribution")
async def get_price_distribution(
    dimension: str = Query("weekly"),
    db=Depends(get_db)
):
    """获取价格分布数据"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    results = db.query(
        Product.category,
        func.avg(Model.payment_amount / Model.payment_quantity).label('avg_price')
    ).join(
        Model, Product.product_id == Model.product_id
    ).filter(
        Model.payment_quantity > 0
    ).group_by(
        Product.category
    ).all()

    distribution = []
    for r in results:
        price = float(r.avg_price or 0)
        if price < 50:
            bucket = "0-50"
        elif price < 100:
            bucket = "50-100"
        elif price < 200:
            bucket = "100-200"
        else:
            bucket = "200+"
        distribution.append({"range": bucket, "count": 1})

    from collections import Counter
    counter = Counter(d['range'] for d in distribution)
    total = sum(counter.values())
    result = []
    for bucket in ["0-50", "50-100", "100-200", "200+"]:
        count = counter.get(bucket, 0)
        result.append({
            "range": bucket,
            "percentage": round(count / total * 100, 1) if total > 0 else 0
        })

    return {"distribution": result}

@router.get("/top-products")
async def get_top_products(
    dimension: str = Query("weekly"),
    limit: int = Query(10),
    db=Depends(get_db)
):
    """获取TOP产品"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    results = db.query(
        Product.product_id,
        Product.title,
        Product.category,
        func.sum(Model.payment_amount).label('gmv')
    ).join(
        Model, Product.product_id == Model.product_id
    ).group_by(
        Product.product_id
    ).order_by(
        func.sum(Model.payment_amount).desc()
    ).limit(limit).all()

    return {
        "products": [{
            "rank": i+1,
            "product_id": r.product_id,
            "name": r.title or "未命名",
            "category": r.category or "",
            "gmv": round(float(r.gmv or 0), 2)
        } for i, r in enumerate(results)]
    }

@router.get("/competition")
async def get_competition_analysis(
    dimension: str = Query("weekly"),
    db=Depends(get_db)
):
    """获取竞争分析数据"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    total_products = db.query(Product).count()
    active_products = db.query(func.count(func.distinct(Model.product_id))).scalar() or 0

    results = db.query(
        Product.category,
        func.count(func.distinct(Model.product_id)).label('active_count')
    ).join(
        Model, Product.product_id == Model.product_id
    ).group_by(
        Product.category
    ).all()

    return {
        "total_products": total_products,
        "active_products": active_products,
        "categories": [{
            "category": r.category or "未分类",
            "active_count": r.active_count
        } for r in results]
    }
