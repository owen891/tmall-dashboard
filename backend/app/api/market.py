from fastapi import APIRouter, Query, Depends
from sqlalchemy import func
from app.models import Product, WeeklyData, DailyData, MonthlyData
from app.core.database import get_db
from typing import Optional

router = APIRouter(prefix="/market", tags=["市场分析"])

@router.get("/overview")
async def get_market_overview(
    dimension: str = Query("weekly", description="时间维度"),
    db=Depends(get_db)
):
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)
    total_products = db.query(func.count(Product.product_id)).filter(Product.status == 'active').scalar() or 0
    total_gmv = db.query(func.sum(Model.payment_amount)).scalar() or 0
    avg_conversion = db.query(func.avg(Model.payment_conversion)).scalar() or 0
    return {
        "code": 200,
        "data": {
            "total_products": total_products,
            "total_gmv": float(total_gmv),
            "avg_conversion": float(avg_conversion),
            "market_trend": "stable",
            "top_categories": [],
            "opportunities": []
        }
    }

@router.get("/keywords")
async def get_market_keywords(
    dimension: str = Query("weekly", description="时间维度"),
    db=Depends(get_db)
):
    return {"code": 200, "data": {"keywords": []}}

@router.get("/opportunities")
async def get_market_opportunities(
    db=Depends(get_db)
):
    return {"code": 200, "data": {"opportunities": []}}

@router.get("/categories")
async def get_market_categories(
    db=Depends(get_db)
):
    return {"code": 200, "data": {"categories": []}}

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


@router.get("/competitors")
async def get_competitor_analysis(
    limit: int = Query(20),
    db=Depends(get_db)
):
    Model = WeeklyData
    results = db.query(
        Product.product_id,
        Product.title,
        Product.category,
        func.sum(Model.payment_amount).label('gmv'),
        func.count(func.distinct(Model.product_id)).label('rank')
    ).join(
        Model, Product.product_id == Model.product_id
    ).group_by(
        Product.product_id, Product.title, Product.category
    ).order_by(
        func.sum(Model.payment_amount).desc()
    ).limit(limit).all()

    total_gmv = db.query(func.sum(Model.payment_amount)).scalar() or 1
    competitors = []
    for i, r in enumerate(results):
        gmv = float(r.gmv or 0)
        share = round(gmv / total_gmv * 100, 2) if total_gmv > 0 else 0
        competitors.append({
            "rank": i + 1,
            "product_name": r.title or "未命名",
            "category": r.category or "未分类",
            "gmv": round(gmv, 2),
            "market_share": share,
            "price_range": "待补充"
        })
    return {"code": 200, "data": competitors}


@router.get("/demand")
async def get_demand_analysis(
    dimension: str = Query("weekly", description="时间维度"),
    db=Depends(get_db)
):
    """需求分析8大维度"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)
    
    total_products = db.query(func.count(Product.product_id)).scalar() or 1
    
    avg_conversion = db.query(func.avg(Model.payment_conversion)).scalar() or 0
    avg_conversion_score = min(100, avg_conversion * 100)
    
    total_gmv = db.query(func.sum(Model.payment_amount)).scalar() or 0
    total_refund = db.query(func.sum(Model.refund_amount)).scalar() or 0
    refund_rate = total_refund / total_gmv if total_gmv > 0 else 0
    refund_score = max(0, 100 - refund_rate * 100)
    
    avg_roi = db.query(func.avg(Model.ad_roi)).scalar() or 0
    roi_score = min(100, avg_roi * 50)
    
    total_ad_spend = db.query(func.sum(Model.ad_spend)).scalar() or 0
    ad_ratio = total_ad_spend / total_gmv if total_gmv > 0 else 0
    ad_score = max(0, 100 - ad_ratio * 100)
    
    avg_order_value = db.query(func.avg(Model.avg_order_value)).scalar() or 0
    price_score = min(100, avg_order_value / 2)
    
    total_visitors = db.query(func.sum(Model.ipv)).scalar() or 0
    demand_volume_score = min(100, total_visitors / 1000)
    
    active_count = db.query(func.count(func.distinct(Model.product_id))).scalar() or 0
    active_ratio = active_count / total_products
    competition_score = max(0, 100 - active_ratio * 100)
    
    inventory_turnover = min(100, 80)
    
    dimensions = [
        {"dimension": "搜索热度", "value": demand_volume_score, "score": round(demand_volume_score, 1), "trend": 5.2, "suggestion": demand_volume_score > 60 and "需求旺盛，可加大推广" or "需提升搜索曝光"},
        {"dimension": "转化率", "value": avg_conversion, "score": round(avg_conversion_score, 1), "trend": 2.1, "suggestion": avg_conversion > 0.05 and "转化良好" or "优化详情页提升转化"},
        {"dimension": "退款率", "value": round(refund_rate, 3), "score": round(refund_score, 1), "trend": -1.5, "suggestion": refund_rate < 0.1 and "退款控制良好" or "关注商品质量"},
        {"dimension": "广告ROI", "value": avg_roi, "score": round(roi_score, 1), "trend": 3.8, "suggestion": avg_roi > 2 and "ROI健康" or "优化投放策略"},
        {"dimension": "广告占比", "value": round(ad_ratio, 3), "score": round(ad_score, 1), "trend": -0.8, "suggestion": ad_ratio < 0.2 and "广告占比合理" or "控制广告预算"},
        {"dimension": "客单价", "value": round(avg_order_value, 2), "score": round(price_score, 1), "trend": 1.2, "suggestion": "通过搭配销售提升客单价"},
        {"dimension": "竞争度", "value": round(active_ratio, 3), "score": round(competition_score, 1), "trend": 0.5, "suggestion": "寻找蓝海细分市场"},
        {"dimension": "库存周转", "value": inventory_turnover, "score": inventory_turnover, "trend": -2.3, "suggestion": "关注滞销款，加快周转"}
    ]
    
    return {"code": 200, "data": {"dimensions": dimensions}}
