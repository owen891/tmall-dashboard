from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.models import Product, WeeklyData, MonthlyData, ProductHealth, Alert
import json

router = APIRouter(prefix="/reports", tags=["自动化报告"])


@router.get("", response_model=ResponseModel)
def get_reports_list(
    db: Session = Depends(get_db)
):
    return ResponseModel(data={
        "reports": [
            {"id": "weekly", "name": "周度汇总报告", "type": "weekly-summary", "frequency": "每周"},
            {"id": "monthly", "name": "月度汇总报告", "type": "monthly-summary", "frequency": "每月"},
            {"id": "health", "name": "健康度报告", "type": "health-report", "frequency": "每周"},
            {"id": "alert", "name": "预警汇总报告", "type": "alert-summary", "frequency": "每日"},
        ],
        "total": 4
    })


@router.get("/weekly-summary", response_model=ResponseModel)
def get_weekly_summary_report(
    period: Optional[str] = Query(None, description="周期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    生成周度汇总报告
    包含GMV、访客、转化、推广等核心指标
    """
    if not period:
        latest = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
        period = latest.week_start if latest else datetime.now().strftime("%Y-%m-%d")
    
    results = db.query(
        func.sum(WeeklyData.payment_amount).label('total_gmv'),
        func.sum(WeeklyData.refund_amount).label('total_refund'),
        func.sum(WeeklyData.ipv).label('total_visitors'),
        func.avg(WeeklyData.payment_conversion).label('avg_conversion'),
        func.sum(WeeklyData.ad_spend).label('total_ad_spend'),
        func.avg(WeeklyData.ad_roi).label('avg_roi'),
        func.count(WeeklyData.id).label('product_count')
    ).filter(WeeklyData.week_start == period).first()
    
    top_products = db.query(Product, WeeklyData).join(
        WeeklyData, Product.product_id == WeeklyData.product_id
    ).filter(
        WeeklyData.week_start == period,
        Product.status == 'active'
    ).order_by(desc(WeeklyData.payment_amount)).limit(10).all()
    
    top_products_data = []
    for product, weekly in top_products:
        top_products_data.append({
            "product_id": product.product_id,
            "title": product.title,
            "gmv": weekly.payment_amount or 0,
            "visitors": weekly.ipv or 0,
            "conversion": round((weekly.payment_conversion or 0) * 100, 2),
            "roi": round(weekly.ad_roi or 0, 2)
        })
    
    return ResponseModel(data={
        "period": period,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_gmv": round(results.total_gmv or 0, 2),
            "total_refund": round(results.total_refund or 0, 2),
            "net_sales": round((results.total_gmv or 0) - (results.total_refund or 0), 2),
            "total_visitors": results.total_visitors or 0,
            "avg_conversion": round((results.avg_conversion or 0) * 100, 2),
            "total_ad_spend": round(results.total_ad_spend or 0, 2),
            "avg_roi": round(results.avg_roi or 0, 2),
            "ad_ratio": round((results.total_ad_spend or 0) / (results.total_gmv or 1) * 100, 2),
            "product_count": results.product_count or 0
        },
        "top_products": top_products_data
    })


@router.get("/monthly-summary", response_model=ResponseModel)
def get_monthly_summary_report(
    month: Optional[str] = Query(None, description="月份 YYYY-MM"),
    db: Session = Depends(get_db)
):
    """
    生成月度汇总报告
    包含更详细的财务和运营指标
    """
    if not month:
        latest = db.query(MonthlyData.month).order_by(desc(MonthlyData.month)).first()
        month = latest.month if latest else datetime.now().strftime("%Y-%m")
    
    results = db.query(
        func.sum(MonthlyData.payment_amount).label('total_gmv'),
        func.sum(MonthlyData.refund_amount).label('total_refund'),
        func.sum(MonthlyData.visitors).label('total_visitors'),
        func.avg(MonthlyData.payment_conversion).label('avg_conversion'),
        func.sum(MonthlyData.ad_spend).label('total_ad_spend'),
        func.avg(MonthlyData.ad_roi).label('avg_roi'),
        func.sum(MonthlyData.buyers).label('total_buyers'),
        func.avg(MonthlyData.avg_order_value).label('avg_order_value'),
        func.sum(MonthlyData.keyword_spend).label('keyword_spend'),
        func.sum(MonthlyData.crowd_spend).label('crowd_spend'),
        func.sum(MonthlyData.site_spend).label('site_spend'),
    ).filter(MonthlyData.month == month).first()
    
    category_stats = db.query(
        Product.category,
        func.sum(MonthlyData.payment_amount).label('gmv'),
        func.count(func.distinct(Product.product_id)).label('product_count')
    ).join(
        MonthlyData, Product.product_id == MonthlyData.product_id
    ).filter(
        MonthlyData.month == month,
        Product.category.isnot(None)
    ).group_by(Product.category).order_by(desc('gmv')).limit(10).all()
    
    category_data = []
    for cat in category_stats:
        category_data.append({
            "category": cat.category,
            "gmv": round(cat.gmv or 0, 2),
            "product_count": cat.product_count or 0
        })
    
    return ResponseModel(data={
        "month": month,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_gmv": round(results.total_gmv or 0, 2),
            "total_refund": round(results.total_refund or 0, 2),
            "net_sales": round((results.total_gmv or 0) - (results.total_refund or 0), 2),
            "total_visitors": results.total_visitors or 0,
            "total_buyers": results.total_buyers or 0,
            "avg_conversion": round((results.avg_conversion or 0) * 100, 2),
            "avg_order_value": round(results.avg_order_value or 0, 2),
            "total_ad_spend": round(results.total_ad_spend or 0, 2),
            "avg_roi": round(results.avg_roi or 0, 2),
            "keyword_spend": round(results.keyword_spend or 0, 2),
            "crowd_spend": round(results.crowd_spend or 0, 2),
            "site_spend": round(results.site_spend or 0, 2),
        },
        "category_breakdown": category_data
    })


@router.get("/health-report", response_model=ResponseModel)
def get_health_report(
    period: Optional[str] = Query(None, description="周期"),
    db: Session = Depends(get_db)
):
    """
    生成健康度报告
    统计各健康等级的分布和预警情况
    """
    if not period:
        period = datetime.now().strftime("%Y-%m-%d")
    
    health_stats = db.query(ProductHealth).filter(
        ProductHealth.period == period
    ).all()
    
    if not health_stats:
        return ResponseModel(data={
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "excellent": 0,
                "good": 0,
                "warning": 0,
                "critical": 0,
                "avg_score": 0,
                "total_products": 0
            },
            "products": []
        })
    
    excellent = sum(1 for h in health_stats if h.health_level == 'excellent')
    good = sum(1 for h in health_stats if h.health_level == 'good')
    warning = sum(1 for h in health_stats if h.health_level == 'warning')
    critical = sum(1 for h in health_stats if h.health_level == 'critical')
    avg_score = sum(h.health_score or 0 for h in health_stats) / len(health_stats)
    
    critical_products = []
    for h in health_stats:
        if h.health_level in ['warning', 'critical']:
            product = db.query(Product).filter(Product.product_id == h.product_id).first()
            if product:
                critical_products.append({
                    "product_id": product.product_id,
                    "title": product.title,
                    "health_score": round(h.health_score or 0, 1),
                    "health_level": h.health_level,
                    "alert_dimensions": h.alert_dimensions
                })
    
    return ResponseModel(data={
        "period": period,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "excellent": excellent,
            "good": good,
            "warning": warning,
            "critical": critical,
            "avg_score": round(avg_score, 1),
            "total_products": len(health_stats)
        },
        "products": critical_products[:20]
    })


@router.get("/alert-summary", response_model=ResponseModel)
def get_alert_summary(
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    db: Session = Depends(get_db)
):
    """
    获取告警汇总
    统计各类型告警的数量和趋势
    """
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    alerts = db.query(Alert).filter(
        Alert.created_at >= start_date
    ).all()
    
    alert_types = {}
    for alert in alerts:
        alert_type = alert.alert_type or 'other'
        if alert_type not in alert_types:
            alert_types[alert_type] = {"total": 0, "critical": 0, "warning": 0, "resolved": 0}
        alert_types[alert_type]["total"] += 1
        if alert.severity == 'critical':
            alert_types[alert_type]["critical"] += 1
        elif alert.severity == 'warning':
            alert_types[alert_type]["warning"] += 1
        if alert.dismissed:
            alert_types[alert_type]["resolved"] += 1
    
    recent_alerts = db.query(Alert).filter(
        Alert.created_at >= start_date
    ).order_by(desc(Alert.created_at)).limit(10).all()
    
    recent_alerts_data = []
    for alert in recent_alerts:
        product = db.query(Product).filter(Product.product_id == alert.product_id).first()
        recent_alerts_data.append({
            "id": alert.id,
            "title": alert.title or f"{alert.alert_type}告警",
            "severity": alert.severity,
            "product_title": product.title if product else alert.product_id,
            "detail": alert.detail,
            "created_at": alert.created_at.isoformat() if alert.created_at else None
        })
    
    return ResponseModel(data={
        "period_days": days,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_alerts": len(alerts),
            "critical_count": sum(1 for a in alerts if a.severity == 'critical'),
            "warning_count": sum(1 for a in alerts if a.severity == 'warning'),
            "resolved_count": sum(1 for a in alerts if a.dismissed)
        },
        "by_type": alert_types,
        "recent_alerts": recent_alerts_data
    })


@router.get("/export/json", response_model=ResponseModel)
def export_report_json(
    report_type: str = Query(..., description="报告类型: weekly/monthly/health/alerts"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """
    导出报告为JSON格式
    """
    if report_type == 'weekly':
        report = get_weekly_summary_report(period, db)
    elif report_type == 'monthly':
        report = get_monthly_summary_report(period, db)
    elif report_type == 'health':
        report = get_health_report(period, db)
    elif report_type == 'alerts':
        report = get_alert_summary(7, db)
    else:
        raise HTTPException(status_code=400, detail="不支持的报告类型")
    
    return report
