from fastapi import APIRouter, Query, Depends
from sqlalchemy import func
from app.models import Product, WeeklyData, DailyData, MonthlyData, PaidDetail
from app.core.database import get_db
from typing import Optional

router = APIRouter(prefix="/promotion", tags=["推广分析"])

@router.get("/summary")
async def get_promotion_summary(
    dimension: str = Query("weekly", description="时间维度: daily, weekly, monthly"),
    db=Depends(get_db)
):
    """获取推广汇总数据"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    total_ad_spend = db.query(func.sum(Model.ad_spend)).filter(Model.ad_spend.isnot(None)).scalar() or 0
    total_payment = db.query(func.sum(Model.payment_amount)).filter(Model.payment_amount.isnot(None)).scalar() or 0
    total_clicks = db.query(func.sum(Model.clicks)).filter(Model.clicks.isnot(None)).scalar() or 0
    total_impressions = db.query(func.sum(Model.impressions)).filter(Model.impressions.isnot(None)).scalar() or 0

    roi = total_ad_spend / total_payment * 100 if total_payment > 0 else 0
    ctr = total_clicks / total_impressions * 100 if total_impressions > 0 else 0

    return {
        "total_ad_spend": round(float(total_ad_spend), 2),
        "total_payment": round(float(total_payment), 2),
        "total_clicks": int(total_clicks) if total_clicks else 0,
        "total_impressions": int(total_impressions) if total_impressions else 0,
        "roi": round(float(roi), 2),
        "ctr": round(float(ctr), 2)
    }

@router.get("/products")
async def get_promotion_products(
    dimension: str = Query("weekly"),
    limit: int = Query(20),
    db=Depends(get_db)
):
    """获取推广产品列表"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    results = db.query(
        Product.product_id,
        Product.title,
        Product.category,
        func.sum(Model.ad_spend).label('ad_spend'),
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.clicks).label('clicks'),
        func.sum(Model.impressions).label('impressions'),
        func.avg(Model.ad_roi).label('roi')
    ).join(
        Model, Product.product_id == Model.product_id
    ).group_by(
        Product.product_id
    ).order_by(
        func.sum(Model.ad_spend).desc()
    ).limit(limit).all()

    products = []
    for r in results:
        payment = float(r.payment or 0)
        ad_spend = float(r.ad_spend or 0)
        roi = payment / ad_spend * 100 if ad_spend > 0 else 0
        products.append({
            "product_id": r.product_id,
            "name": r.title or "未命名",
            "category": r.category or "",
            "ad_spend": round(ad_spend, 2),
            "payment": round(payment, 2),
            "clicks": int(r.clicks) if r.clicks else 0,
            "impressions": int(r.impressions) if r.impressions else 0,
            "roi": round(float(roi), 2)
        })

    return {"products": products}

@router.get("/trends")
async def get_promotion_trends(
    dimension: str = Query("weekly"),
    limit: int = Query(12),
    db=Depends(get_db)
):
    """获取推广趋势数据"""
    Model = WeeklyData if dimension == "weekly" else (DailyData if dimension == "daily" else MonthlyData)

    date_col = Model.week_start if dimension == "weekly" else (Model.date if dimension == "daily" else Model.month)

    results = db.query(
        date_col,
        func.sum(Model.ad_spend).label('ad_spend'),
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.clicks).label('clicks'),
        func.sum(Model.impressions).label('impressions')
    ).group_by(
        date_col
    ).order_by(
        date_col.desc()
    ).limit(limit).all()

    trend = []
    for r in results:
        payment = float(r.payment or 0)
        ad_spend = float(r.ad_spend or 0)
        trend.append({
            "date": str(r.week_start if dimension == "weekly" else (r.date if dimension == "daily" else r.month)),
            "ad_spend": round(ad_spend, 2),
            "payment": round(payment, 2),
            "clicks": int(r.clicks) if r.clicks else 0,
            "impressions": int(r.impressions) if r.impressions else 0,
            "roi": round(payment / ad_spend * 100 if ad_spend > 0 else 0, 2)
        })

    trend.reverse()
    return {"trend": trend}
