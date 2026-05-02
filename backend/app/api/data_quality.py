from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.models import Product, WeeklyData, MonthlyData, DailyData

router = APIRouter(prefix="/data-quality", tags=["数据质量"])


@router.get("/overview", response_model=ResponseModel)
def get_data_quality_overview(db: Session = Depends(get_db)):
    """
    数据质量概览
    """
    total_products = db.query(Product).count()
    active_products = db.query(Product).filter(Product.status == 'active').count()
    
    latest_week = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
    week_start = latest_week.week_start if latest_week else None
    
    weekly_data_count = db.query(WeeklyData).filter(
        WeeklyData.week_start == week_start
    ).count() if week_start else 0
    
    products_with_data = db.query(func.count(func.distinct(WeeklyData.product_id))).filter(
        WeeklyData.week_start == week_start
    ).scalar() if week_start else 0
    
    return ResponseModel(data={
        "total_products": total_products,
        "active_products": active_products,
        "weekly_data_count": weekly_data_count,
        "products_with_data": products_with_data,
        "coverage_rate": round(products_with_data / active_products * 100, 2) if active_products > 0 else 0
    })


@router.get("/missing-values", response_model=ResponseModel)
def get_missing_values(
    period: Optional[str] = Query(None, description="周期"),
    db: Session = Depends(get_db)
):
    """
    缺失值检测
    检测各字段的缺失情况
    """
    if not period:
        latest = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
        period = latest.week_start if latest else None
    
    if not period:
        return ResponseModel(data={"fields": [], "message": "无数据"})
    
    total = db.query(WeeklyData).filter(WeeklyData.week_start == period).count()
    
    if total == 0:
        return ResponseModel(data={"fields": [], "message": "无数据"})
    
    fields_to_check = [
        ('payment_amount', '支付金额'),
        ('refund_amount', '退款金额'),
        ('ipv', '访客数'),
        ('payment_conversion', '支付转化率'),
        ('ad_spend', '广告花费'),
        ('ad_roi', '广告ROI'),
        ('avg_order_value', '客单价'),
        ('cart_rate', '加购率'),
    ]
    
    field_stats = []
    for field, label in fields_to_check:
        null_count = db.query(func.count(WeeklyData.id)).filter(
            WeeklyData.week_start == period,
            getattr(WeeklyData, field).is_(None)
        ).scalar()
        
        zero_count = db.query(func.count(WeeklyData.id)).filter(
            WeeklyData.week_start == period,
            getattr(WeeklyData, field) == 0
        ).scalar()
        
        missing_rate = round((null_count + zero_count) / total * 100, 2)
        
        field_stats.append({
            "field": field,
            "label": label,
            "total": total,
            "null_count": null_count,
            "zero_count": zero_count,
            "missing_rate": missing_rate,
            "status": "critical" if missing_rate > 30 else "warning" if missing_rate > 10 else "good"
        })
    
    field_stats.sort(key=lambda x: x["missing_rate"], reverse=True)
    
    return ResponseModel(data={
        "period": period,
        "total_records": total,
        "fields": field_stats
    })


@router.get("/anomalies", response_model=ResponseModel)
def get_anomalies(
    period: Optional[str] = Query(None, description="周期"),
    db: Session = Depends(get_db)
):
    """
    异常值检测
    检测数据中的异常值
    """
    if not period:
        latest = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
        period = latest.week_start if latest else None
    
    if not period:
        return ResponseModel(data={"anomalies": [], "message": "无数据"})
    
    data = db.query(Product, WeeklyData).join(
        WeeklyData, Product.product_id == WeeklyData.product_id
    ).filter(WeeklyData.week_start == period).all()
    
    anomalies = []
    
    for product, weekly in data:
        issues = []
        
        if weekly.payment_amount and weekly.payment_amount < 0:
            issues.append({"field": "payment_amount", "issue": "负值"})
        
        if weekly.ad_roi and weekly.ad_roi < 0:
            issues.append({"field": "ad_roi", "issue": "ROI为负"})
        
        if weekly.payment_conversion and (weekly.payment_conversion < 0 or weekly.payment_conversion > 1):
            issues.append({"field": "payment_conversion", "issue": "转化率超出范围"})
        
        if weekly.refund_rate and weekly.refund_rate > 0.5:
            issues.append({"field": "refund_rate", "issue": "退款率异常高"})
        
        if weekly.ipv and weekly.payment_amount:
            expected_conversion = weekly.payment_amount / weekly.ipv / 100
            if weekly.payment_conversion and abs(weekly.payment_conversion - expected_conversion) > 0.1:
                issues.append({"field": "data_inconsistency", "issue": "数据不一致"})
        
        if issues:
            anomalies.append({
                "product_id": product.product_id,
                "title": product.title[:40] + "..." if len(product.title) > 40 else product.title,
                "issues": issues,
                "severity": "critical" if len(issues) > 1 else "warning"
            })
    
    anomalies.sort(key=lambda x: len(x["issues"]), reverse=True)
    
    return ResponseModel(data={
        "period": period,
        "total_anomalies": len(anomalies),
        "anomalies": anomalies[:50]
    })


@router.get("/freshness", response_model=ResponseModel)
def get_data_freshness(db: Session = Depends(get_db)):
    """
    数据新鲜度
    检测数据更新时间
    """
    latest_weekly = db.query(WeeklyData).order_by(
        desc(WeeklyData.imported_at)
    ).first()
    
    latest_daily = db.query(DailyData).order_by(
        desc(DailyData.imported_at)
    ).first()
    
    latest_monthly = db.query(MonthlyData).order_by(
        desc(MonthlyData.imported_at)
    ).first()
    
    now = datetime.now()
    
    def get_age_hours(dt):
        if not dt or not dt.imported_at:
            return None
        delta = now - dt.imported_at
        return round(delta.total_seconds() / 3600, 1)
    
    return ResponseModel(data={
        "weekly": {
            "latest_date": latest_weekly.week_start if latest_weekly else None,
            "imported_at": latest_weekly.imported_at.isoformat() if latest_weekly and latest_weekly.imported_at else None,
            "age_hours": get_age_hours(latest_weekly),
            "status": "fresh" if get_age_hours(latest_weekly) and get_age_hours(latest_weekly) < 168 else "stale"
        },
        "daily": {
            "latest_date": latest_daily.date if latest_daily else None,
            "imported_at": latest_daily.imported_at.isoformat() if latest_daily and latest_daily.imported_at else None,
            "age_hours": get_age_hours(latest_daily),
            "status": "fresh" if get_age_hours(latest_daily) and get_age_hours(latest_daily) < 24 else "stale"
        },
        "monthly": {
            "latest_date": latest_monthly.month if latest_monthly else None,
            "imported_at": latest_monthly.imported_at.isoformat() if latest_monthly and latest_monthly.imported_at else None,
            "age_hours": get_age_hours(latest_monthly),
            "status": "fresh" if get_age_hours(latest_monthly) and get_age_hours(latest_monthly) < 720 else "stale"
        }
    })


@router.get("/completeness", response_model=ResponseModel)
def get_data_completeness(db: Session = Depends(get_db)):
    """
    数据完整性报告
    """
    total_products = db.query(Product).filter(Product.status == 'active').count()
    
    periods = db.query(WeeklyData.week_start).distinct().order_by(
        desc(WeeklyData.week_start)
    ).limit(4).all()
    
    completeness = []
    for p in periods:
        count = db.query(func.count(func.distinct(WeeklyData.product_id))).filter(
            WeeklyData.week_start == p.week_start
        ).scalar()
        
        completeness.append({
            "period": p.week_start,
            "product_count": count,
            "completeness_rate": round(count / total_products * 100, 2) if total_products > 0 else 0
        })
    
    return ResponseModel(data={
        "total_products": total_products,
        "periods": completeness
    })
