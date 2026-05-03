from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.core.database import get_db
from app.models.dashboard_models import (
    DailyMetrics, MonthlyTarget, TrafficStructure
)

router = APIRouter(prefix="/api/dashboard", tags=["驾驶舱"])


@router.get("/metrics")
async def get_core_metrics(
    date: Optional[str] = Query(None, description="日期，默认为今日"),
    db: Session = Depends(get_db)
):
    """核心指标卡片"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    today = db.query(DailyMetrics).filter(
        DailyMetrics.date == date
    ).first()
    
    yesterday = db.query(DailyMetrics).filter(
        DailyMetrics.date == (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    ).first()
    
    gmv_today = today.gmv if today else 0
    gmv_yesterday = yesterday.gmv if yesterday else 0
    gmv_change = ((gmv_today - gmv_yesterday) / gmv_yesterday * 100) if gmv_yesterday > 0 else 0
    
    return {
        "gmv_today": gmv_today,
        "gmv_yesterday": gmv_yesterday,
        "gmv_change": round(gmv_change, 2),
        "uv": today.total_uv if today else 0,
        "cvr": today.conversion_rate if today else 0,
        "avg_order": today.avg_order_value if today else 0,
        "uv_value": today.uv_value if today else 0,
        "gross_margin": today.gross_margin if today else 0,
        "ad_spend": today.ad_spend if today else 0,
        "ad_roi": today.ad_roi if today else 0,
        "refund_rate": today.refund_rate if today else 0,
        "date": date
    }


@router.get("/target")
async def get_target_progress(
    month: Optional[str] = Query(None, description="月份，默认为当前月"),
    db: Session = Depends(get_db)
):
    """目标进度"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    target = db.query(MonthlyTarget).filter(
        MonthlyTarget.month == month
    ).first()
    
    daily = db.query(func.sum(DailyMetrics.gmv)).filter(
        DailyMetrics.date.like(f"{month}%")
    ).scalar() or 0
    
    days_in_month = 30
    current_day = datetime.now().day
    time_progress = (current_day / days_in_month) * 100
    
    target_gmv = target.target_gmv if target else 0
    actual_gmv = target.actual_gmv if target else daily
    completion_rate = (actual_gmv / target_gmv * 100) if target_gmv > 0 else 0
    
    alert = "normal"
    if completion_rate < time_progress * 0.8:
        alert = "danger"
    elif completion_rate < time_progress:
        alert = "warning"
    
    return {
        "target_gmv": target_gmv,
        "actual_gmv": actual_gmv,
        "completion_rate": round(completion_rate, 2),
        "time_progress": round(time_progress, 2),
        "time_remaining": days_in_month - current_day,
        "alert": alert,
        "month": month
    }


@router.get("/traffic")
async def get_traffic_structure(
    date: Optional[str] = Query(None, description="日期，默认为今日"),
    db: Session = Depends(get_db)
):
    """流量结构"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    traffic = db.query(TrafficStructure).filter(
        TrafficStructure.date == date
    ).first()
    
    if not traffic:
        return {
            "search_pct": 0,
            "recommend_pct": 0,
            "paid_pct": 0,
            "free_pct": 0,
            "total_uv": 0,
            "date": date
        }
    
    return {
        "search_pct": traffic.search_pct,
        "recommend_pct": traffic.recommend_pct,
        "paid_pct": traffic.paid_pct,
        "free_pct": traffic.free_pct,
        "total_uv": traffic.total_uv,
        "search_uv": traffic.search_uv,
        "recommend_uv": traffic.recommend_uv,
        "ztc_uv": traffic.ztc_uv,
        "wxt_uv": traffic.wxt_uv,
        "date": date
    }


@router.get("/kpi-cards")
async def get_kpi_cards(
    date: Optional[str] = Query(None, description="日期，默认为今日"),
    db: Session = Depends(get_db)
):
    """KPI指标卡片"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    today = db.query(DailyMetrics).filter(
        DailyMetrics.date == date
    ).first()
    
    yesterday_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = db.query(DailyMetrics).filter(
        DailyMetrics.date == yesterday_date
    ).first()
    
    def calc_change(current, prev):
        if not prev or prev == 0:
            return 0
        return round((current - prev) / prev * 100, 2)
    
    return {
        "items": [
            {
                "label": "GMV",
                "value": today.gmv if today else 0,
                "change": calc_change(today.gmv if today else 0, yesterday.gmv if yesterday else 0),
                "unit": "¥",
                "icon": "Money"
            },
            {
                "label": "访客数",
                "value": today.total_uv if today else 0,
                "change": calc_change(today.total_uv if today else 0, yesterday.total_uv if yesterday else 0),
                "unit": "",
                "icon": "User"
            },
            {
                "label": "转化率",
                "value": (today.conversion_rate * 100) if today else 0,
                "change": calc_change(today.conversion_rate if today else 0, yesterday.conversion_rate if yesterday else 0),
                "unit": "%",
                "icon": "TrendCharts"
            },
            {
                "label": "客单价",
                "value": today.avg_order_value if today else 0,
                "change": calc_change(today.avg_order_value if today else 0, yesterday.avg_order_value if yesterday else 0),
                "unit": "¥",
                "icon": "ShoppingCart"
            },
            {
                "label": "广告ROI",
                "value": today.ad_roi if today else 0,
                "change": calc_change(today.ad_roi if today else 0, yesterday.ad_roi if yesterday else 0),
                "unit": "",
                "icon": "DataLine"
            },
            {
                "label": "毛利率",
                "value": (today.gross_margin * 100) if today else 0,
                "change": calc_change(today.gross_margin if today else 0, yesterday.gross_margin if yesterday else 0),
                "unit": "%",
                "icon": "Coin"
            }
        ]
    }


@router.get("/trend")
async def get_gmv_trend(
    days: int = Query(7, ge=1, le=30, description="天数"),
    db: Session = Depends(get_db)
):
    """GMV趋势"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    
    metrics = db.query(DailyMetrics).filter(
        DailyMetrics.date >= start_date.strftime("%Y-%m-%d"),
        DailyMetrics.date <= end_date.strftime("%Y-%m-%d")
    ).order_by(DailyMetrics.date).all()
    
    return {
        "items": [
            {
                "date": m.date,
                "gmv": m.gmv,
                "uv": m.total_uv,
                "cvr": m.conversion_rate,
                "avg_order": m.avg_order_value
            }
            for m in metrics
        ]
    }


@router.get("/top-products")
async def get_top_products(
    limit: int = Query(10, ge=1, le=50, description="数量"),
    db: Session = Depends(get_db)
):
    """热销商品TOP"""
    from app.models.dashboard_models import ProductRanking
    
    products = db.query(ProductRanking).order_by(
        desc(ProductRanking.sales_30d)
    ).limit(limit).all()
    
    return {
        "items": [
            {
                "product_id": p.product_id,
                "title": p.title,
                "sales_30d": p.sales_30d,
                "rank": idx + 1,
                "rank_change": p.rank_change,
                "ctr": p.ctr,
                "cvr": p.cvr,
                "tier": p.tier
            }
            for idx, p in enumerate(products)
        ]
    }
