from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from app.core.database import get_db
from app.models import ProductHealth, Product, WeeklyData
from app.schemas.common import ResponseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/health", tags=["健康度评分"])


def calculate_health_score(product_id: str, period: str, db: Session) -> dict:
    """计算商品健康度评分"""
    
    current_date = datetime.strptime(period, "%Y-%m-%d").date()
    prev_date = current_date - timedelta(days=7)
    
    current = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id,
        WeeklyData.week_start == current_date
    ).first()
    
    prev = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id,
        WeeklyData.week_start == prev_date
    ).first()
    
    if not current:
        return None
    
    scores = {}
    
    if current.payment_amount and current.payment_amount > 0:
        scores['sales_score'] = min(100, current.payment_amount / 10000 * 20)
    else:
        scores['sales_score'] = 0
    
    scores['conversion_score'] = min(100, (current.payment_conversion or 0) * 20)
    
    scores['roi_score'] = min(100, (current.ad_roi or 0) * 10) if current.ad_roi and current.ad_roi > 0 else 50
    
    refund_rate = (current.refund_amount / current.payment_amount * 100) if current.payment_amount > 0 else 0
    scores['refund_score'] = max(0, 100 - refund_rate * 10)
    
    if current and prev:
        gmv_change = ((current.payment_amount - prev.payment_amount) / prev.payment_amount * 100) if prev.payment_amount > 0 else 0
        scores['growth_score'] = max(0, min(100, 50 + gmv_change))
        
        ad_change = ((current.ad_spend - prev.ad_spend) / prev.ad_spend * 100) if prev.ad_spend > 0 else 0
        scores['ad_spend_change_score'] = 100 - abs(ad_change) if ad_change < 0 else 100
        
        roi_change = ((current.ad_roi - prev.ad_roi) / prev.ad_roi * 100) if prev.ad_roi and prev.ad_roi > 0 else 0
        scores['roi_change_score'] = max(0, min(100, 50 + roi_change))
    else:
        scores['growth_score'] = 50
        scores['ad_spend_change_score'] = 50
        scores['roi_change_score'] = 50
    
    scores['cart_rate_score'] = min(100, (current.cart_rate or 0) * 20)
    
    search_ratio = (current.search_ipv / current.ipv * 100) if current.ipv > 0 else 0
    scores['search_ratio_score'] = min(100, search_ratio)
    
    scores['repurchase_rate_score'] = min(100, (current.repurchase_rate or 0) * 10)
    
    scores['cross_sell_rate_score'] = min(100, (current.cross_sell_rate or 0) * 20)
    
    if current.industry_ctr and current.industry_ctr > 0:
        search_ctr = (current.search_click_rate or 0)
        scores['search_ctr_vs_industry_score'] = min(100, (search_ctr / current.industry_ctr) * 50) if current.industry_ctr > 0 else 50
    else:
        scores['search_ctr_vs_industry_score'] = 50
    
    scores['review_score'] = 80
    
    total_score = (
        scores['sales_score'] * 0.2 +
        scores['conversion_score'] * 0.15 +
        scores['roi_score'] * 0.15 +
        scores['refund_score'] * 0.1 +
        scores['growth_score'] * 0.15 +
        scores['review_score'] * 0.05 +
        scores['cart_rate_score'] * 0.05 +
        scores['search_ratio_score'] * 0.05 +
        scores['repurchase_rate_score'] * 0.05 +
        scores['cross_sell_rate_score'] * 0.05
    )
    
    scores['health_score'] = round(total_score, 1)
    
    if total_score >= 80:
        scores['health_level'] = 'excellent'
    elif total_score >= 60:
        scores['health_level'] = 'good'
    elif total_score >= 40:
        scores['health_level'] = 'warning'
    else:
        scores['health_level'] = 'danger'
    
    alert_dimensions = []
    if scores['refund_score'] < 50:
        alert_dimensions.append('退款率过高')
    if scores['growth_score'] < 40:
        alert_dimensions.append('增长放缓')
    if scores['roi_score'] < 40:
        alert_dimensions.append('ROI过低')
    if scores['conversion_score'] < 30:
        alert_dimensions.append('转化率低')
    
    scores['alert_dimensions'] = alert_dimensions
    
    return scores


@router.get("/product/{product_id}", response_model=ResponseModel)
def get_product_health(
    product_id: str,
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取商品健康度评分"""
    
    if not period:
        latest = db.query(WeeklyData).filter(
            WeeklyData.product_id == product_id
        ).order_by(desc(WeeklyData.week_start)).first()
        period = latest.week_start.isoformat() if latest else None
    
    if not period:
        return ResponseModel(data={"health": None, "message": "无数据"})
    
    health = db.query(ProductHealth).filter(
        ProductHealth.product_id == product_id,
        ProductHealth.period == period
    ).first()
    
    if not health:
        scores = calculate_health_score(product_id, period, db)
        if not scores:
            return ResponseModel(data={"health": None, "message": "无法计算"})
        
        health = ProductHealth(
            product_id=product_id,
            period=period,
            **scores
        )
        db.add(health)
        db.commit()
        db.refresh(health)
    
    product = db.query(Product).filter(Product.product_id == product_id).first()
    
    return ResponseModel(data={
        "product_id": product_id,
        "title": product.title if product else None,
        "period": period,
        "health": {
            "sales_score": health.sales_score,
            "conversion_score": health.conversion_score,
            "roi_score": health.roi_score,
            "refund_score": health.refund_score,
            "growth_score": health.growth_score,
            "review_score": health.review_score,
            "cart_rate_score": health.cart_rate_score,
            "search_ratio_score": health.search_ratio_score,
            "repurchase_rate_score": health.repurchase_rate_score,
            "cross_sell_rate_score": health.cross_sell_rate_score,
            "health_score": health.health_score,
            "health_level": health.health_level,
            "alert_dimensions": health.alert_dimensions or []
        }
    })


@router.get("/list", response_model=ResponseModel)
def get_health_ranking(
    limit: int = Query(50, description="返回数量"),
    sort_by: str = Query("health_score", description="排序字段"),
    min_score: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """获取健康度排名"""
    
    health_list = db.query(ProductHealth).filter(
        ProductHealth.health_score > 0
    ).order_by(desc(ProductHealth.health_score)).limit(limit).all()
    
    if not health_list:
        return ResponseModel(data={"ranking": [], "count": 0})
    
    result = []
    for h in health_list:
        if min_score and h.health_score < min_score:
            continue
        
        product = db.query(Product).filter(Product.product_id == h.product_id).first()
        
        result.append({
            "product_id": h.product_id,
            "title": product.title if product else None,
            "tier": product.tier if product else None,
            "period": h.period,
            "health_score": h.health_score,
            "health_level": h.health_level,
            "sales_score": h.sales_score,
            "conversion_score": h.conversion_score,
            "roi_score": h.roi_score,
            "growth_score": h.growth_score,
            "alert_dimensions": h.alert_dimensions or []
        })
    
    result.sort(key=lambda x: x["health_score"], reverse=True)
    
    return ResponseModel(data={
        "ranking": result[:limit],
        "count": len(result)
    })


@router.get("/distribution", response_model=ResponseModel)
def get_health_distribution(db: Session = Depends(get_db)):
    """获取健康度分布统计"""
    
    all_health = db.query(ProductHealth).all()
    
    if not all_health:
        return ResponseModel(data={"distribution": {}})
    
    distribution = {
        "excellent": 0,
        "good": 0,
        "warning": 0,
        "danger": 0
    }
    
    total = len(all_health)
    
    for h in all_health:
        level = h.health_level or "unknown"
        if level in distribution:
            distribution[level] += 1
    
    distribution_pct = {
        level: round(count / total * 100, 1)
        for level, count in distribution.items()
    }
    
    avg_scores = {
        "sales": 0,
        "conversion": 0,
        "roi": 0,
        "growth": 0,
        "overall": 0
    }
    
    for h in all_health:
        avg_scores["sales"] += h.sales_score or 0
        avg_scores["conversion"] += h.conversion_score or 0
        avg_scores["roi"] += h.roi_score or 0
        avg_scores["growth"] += h.growth_score or 0
        avg_scores["overall"] += h.health_score or 0
    
    avg_scores = {
        key: round(value / total, 1)
        for key, value in avg_scores.items()
    }
    
    return ResponseModel(data={
        "total_products": total,
        "distribution": distribution,
        "distribution_pct": distribution_pct,
        "average_scores": avg_scores
    })


@router.get("/alerts", response_model=ResponseModel)
def get_health_alerts(
    level: Optional[str] = Query(None, description="告警级别: warning/danger"),
    limit: int = Query(30, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取健康度告警商品"""
    
    query = db.query(ProductHealth)
    
    if level == "danger":
        query = query.filter(ProductHealth.health_level == "danger")
    elif level == "warning":
        query = query.filter(ProductHealth.health_level.in_(["warning", "danger"]))
    else:
        query = query.filter(ProductHealth.health_level.in_(["warning", "danger"]))
    
    alerts = query.order_by(ProductHealth.health_score.asc()).limit(limit).all()
    
    result = []
    for h in alerts:
        product = db.query(Product).filter(Product.product_id == h.product_id).first()
        
        result.append({
            "product_id": h.product_id,
            "title": product.title if product else None,
            "tier": product.tier if product else None,
            "health_score": h.health_score,
            "health_level": h.health_level,
            "period": h.period,
            "alert_dimensions": h.alert_dimensions or []
        })
    
    return ResponseModel(data={
        "alerts": result,
        "count": len(result)
    })


@router.post("/refresh/{product_id}", response_model=ResponseModel)
def refresh_health_score(product_id: str, db: Session = Depends(get_db)):
    """刷新商品健康度评分"""
    
    latest = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id
    ).order_by(desc(WeeklyData.week_start)).first()
    
    if not latest:
        return ResponseModel(data={"message": "无数据"})
    
    period = latest.week_start.isoformat()
    
    existing = db.query(ProductHealth).filter(
        ProductHealth.product_id == product_id,
        ProductHealth.period == period
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
    
    scores = calculate_health_score(product_id, period, db)
    
    health = ProductHealth(
        product_id=product_id,
        period=period,
        **scores
    )
    db.add(health)
    db.commit()
    db.refresh(health)
    
    return ResponseModel(data={
        "message": "健康度评分已刷新",
        "health_score": health.health_score,
        "health_level": health.health_level
    })
