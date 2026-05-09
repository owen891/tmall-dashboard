"""
目标进度与预算 Pace 监控 API
实现"时间进度 vs 销售进度"对比，预算消耗监控
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.utils import get_data_model, get_latest_period, safe_float, DIMENSION_MAP
from app.models import (
    WeeklyData, MonthlyData, DailyData, Product, 
    ShopTarget, ProductTarget, Alert
)
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/pace", tags=["Pace监控"])


def get_period_progress(dimension: str = "weekly") -> dict:
    """计算当前周期的时间进度"""
    now = datetime.now()
    
    if dimension == "monthly":
        days_in_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        days_in_month = days_in_month.day
        elapsed_days = now.day
        progress = (elapsed_days / days_in_month) * 100
        period_name = now.strftime("%Y-%m")
    elif dimension == "yearly":
        start_of_year = datetime(now.year, 1, 1)
        end_of_year = datetime(now.year + 1, 1, 1)
        total_days = (end_of_year - start_of_year).days
        elapsed_days = (now - start_of_year).days
        progress = (elapsed_days / total_days) * 100
        period_name = str(now.year)
    else:
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        elapsed_days = (now - start_of_week).days + 1
        progress = (elapsed_days / 7) * 100
        period_name = start_of_week.strftime("%Y-%m-%d")
    
    return {
        "period": period_name,
        "progress": round(progress, 1),
        "elapsed_days": elapsed_days if dimension != "yearly" else None,
        "total_days": 7 if dimension == "weekly" else (days_in_month if dimension == "monthly" else 365)
    }


def calculate_pace_status(time_progress: float, sales_progress: float) -> dict:
    """计算 Pace 状态"""
    gap = sales_progress - time_progress
    
    if gap >= 5:
        status = "ahead"
        level = "success"
        message = "进度领先，保持当前节奏"
    elif gap >= -5:
        status = "on_track"
        level = "info"
        message = "进度正常，持续关注"
    elif gap >= -15:
        status = "behind"
        level = "warning"
        message = "进度落后，需要加速"
    else:
        status = "critical"
        level = "danger"
        message = "进度严重落后，需要立即行动"
    
    return {
        "status": status,
        "level": level,
        "message": message,
        "gap": round(gap, 1)
    }


@router.get("/overview", response_model=ResponseModel)
def get_pace_overview(
    dimension: str = Query("monthly", description="时间维度: weekly/monthly/yearly"),
    db: Session = Depends(get_db)
):
    time_info = get_period_progress(dimension)
    time_progress = time_info["progress"]
    
    targets = db.query(ShopTarget).filter(
        ShopTarget.period.like(f"{datetime.now().year}%")
    ).all()
    
    if not targets:
        return ResponseModel(data={
            "time_progress": time_info,
            "sales_progress": {"progress": 0, "current": 0, "target": 0},
            "pace_status": {"status": "no_target", "level": "info", "message": "未设置目标", "gap": 0},
            "budget_pace": None,
            "alerts": []
        })
    
    target_gmv = sum(safe_float(t.target_gsv) for t in targets)
    target_budget = sum(safe_float(t.target_ad_spend) for t in targets)
    
    if dimension == "yearly":
        Model = MonthlyData
        date_col = 'month'
        visitors_col = 'visitors'
    else:
        dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['monthly'])
        Model, date_col, visitors_col = get_data_model(dimension)
    
    if dimension == "yearly":
        current_gmv = db.query(func.sum(Model.payment_amount)).filter(
            func.strftime('%Y', getattr(Model, date_col)) == str(datetime.now().year)
        ).scalar() or 0
        current_visitors = db.query(func.sum(getattr(Model, visitors_col))).filter(
            func.strftime('%Y', getattr(Model, date_col)) == str(datetime.now().year)
        ).scalar() or 0
        current_ad_spend = db.query(func.sum(Model.ad_spend)).filter(
            func.strftime('%Y', getattr(Model, date_col)) == str(datetime.now().year)
        ).scalar() or 0
    else:
        current_gmv = db.query(func.sum(Model.payment_amount)).scalar() or 0
        current_visitors = db.query(func.sum(getattr(Model, visitors_col))).scalar() or 0
        current_ad_spend = db.query(func.sum(Model.ad_spend)).scalar() or 0
    
    current_gmv = safe_float(current_gmv)
    current_visitors = safe_float(current_visitors)
    current_ad_spend = safe_float(current_ad_spend)
    
    sales_progress = (current_gmv / target_gmv * 100) if target_gmv > 0 else 0
    budget_progress = (current_ad_spend / target_budget * 100) if target_budget > 0 else 0
    
    pace_status = calculate_pace_status(time_progress, sales_progress)
    
    budget_pace = None
    if target_budget > 0:
        budget_gap = budget_progress - time_progress
        if budget_gap > 10:
            budget_status = "overspend"
            budget_level = "danger"
            budget_message = "预算超支，需要控制投放"
        elif budget_gap > 0:
            budget_status = "fast"
            budget_level = "warning"
            budget_message = "预算消耗偏快，注意控制"
        elif budget_gap > -10:
            budget_status = "normal"
            budget_level = "info"
            budget_message = "预算消耗正常"
        else:
            budget_status = "slow"
            budget_level = "success"
            budget_message = "预算消耗偏慢，可加大投放"
        
        budget_pace = {
            "target": round(target_budget, 2),
            "current": round(current_ad_spend, 2),
            "progress": round(budget_progress, 1),
            "time_progress": time_progress,
            "gap": round(budget_gap, 1),
            "status": budget_status,
            "level": budget_level,
            "message": budget_message
        }
    
    return ResponseModel(data={
        "dimension": dimension,
        "time_progress": time_info,
        "sales_progress": {
            "target": round(target_gmv, 2),
            "current": round(current_gmv, 2),
            "progress": round(sales_progress, 1),
            "gap_to_target": round(target_gmv - current_gmv, 2),
            "daily_needed": round((target_gmv - current_gmv) / max(1, time_info.get("total_days", 30) - time_info.get("elapsed_days", 15)), 2) if time_info.get("elapsed_days") else 0
        },
        "visitors_progress": {
            "target": int(current_visitors),
            "current": int(current_visitors),
            "progress": 0
        },
        "pace_status": pace_status,
        "budget_pace": budget_pace,
        "alerts": generate_pace_alerts(pace_status, budget_pace)
    })


def generate_pace_alerts(pace_status: dict, budget_pace: dict) -> List[dict]:
    """生成 Pace 预警"""
    alerts = []
    
    if pace_status["status"] == "behind":
        alerts.append({
            "type": "sales_pace",
            "level": "warning",
            "message": f"销售进度落后时间进度 {abs(pace_status['gap'])}%，需要加速推广"
        })
    elif pace_status["status"] == "critical":
        alerts.append({
            "type": "sales_pace",
            "level": "danger",
            "message": f"销售进度严重落后 {abs(pace_status['gap'])}%，需要立即采取行动"
        })
    
    if budget_pace and budget_pace["status"] == "overspend":
        alerts.append({
            "type": "budget_pace",
            "level": "danger",
            "message": f"预算超支 {budget_pace['gap']}%，建议优化投放策略"
        })
    
    return alerts


@router.get("/products", response_model=ResponseModel)
def get_product_pace(
    dimension: str = Query("monthly", description="时间维度"),
    db: Session = Depends(get_db)
):
    time_info = get_period_progress(dimension)
    time_progress = time_info["progress"]
    
    targets = db.query(ProductTarget).all()
    
    if not targets:
        return ResponseModel(data={"products": [], "time_progress": time_info})
    
    product_paces = []
    
    for target in targets:
        product = db.query(Product).filter(Product.product_id == target.product_id).first()
        if not product:
            continue
        
        if dimension == "yearly":
            Model = MonthlyData
            date_col = 'month'
        else:
            Model, date_col, _ = get_data_model(dimension)
        
        if dimension == "yearly":
            current_gmv = db.query(func.sum(Model.payment_amount)).filter(
                Model.product_id == target.product_id,
                func.strftime('%Y', getattr(Model, date_col)) == str(datetime.now().year)
            ).scalar() or 0
        else:
            current_gmv = db.query(func.sum(Model.payment_amount)).filter(
                Model.product_id == target.product_id
            ).scalar() or 0
        
        current_gmv = safe_float(current_gmv)
        target_gmv = safe_float(target.target_gsv)
        
        progress = (current_gmv / target_gmv * 100) if target_gmv > 0 else 0
        pace_status = calculate_pace_status(time_progress, progress)
        
        product_paces.append({
            "product_id": target.product_id,
            "title": product.title,
            "tier": product.tier,
            "target_gmv": round(target_gmv, 2),
            "current_gmv": round(current_gmv, 2),
            "progress": round(progress, 1),
            "time_progress": time_progress,
            "gap": round(progress - time_progress, 1),
            "status": pace_status["status"],
            "level": pace_status["level"],
            "message": pace_status["message"]
        })
    
    product_paces.sort(key=lambda x: x["gap"])
    
    return ResponseModel(data={
        "dimension": dimension,
        "time_progress": time_info,
        "products": product_paces
    })


@router.get("/history", response_model=ResponseModel)
def get_pace_history(
    dimension: str = Query("monthly", description="时间维度"),
    periods: int = Query(12, description="历史周期数"),
    db: Session = Depends(get_db)
):
    if dimension == "yearly":
        Model = MonthlyData
        date_col = 'month'
    else:
        Model, date_col, visitors_col = get_data_model(dimension)
    
    latest_periods = db.query(getattr(Model, date_col)).distinct().order_by(
        desc(getattr(Model, date_col))
    ).limit(periods).all()
    
    history = []
    targets = db.query(ShopTarget).all()
    target_gmv = sum(safe_float(t.target_gsv) for t in targets) / max(1, len(targets)) if targets else 0
    
    for period_row in reversed(latest_periods):
        period = period_row[0]
        if hasattr(period, 'isoformat'):
            period_str = period.isoformat()
        else:
            period_str = str(period)
        
        gmv = db.query(func.sum(Model.payment_amount)).filter(
            getattr(Model, date_col) == period
        ).scalar() or 0
        
        gmv = safe_float(gmv)
        progress = (gmv / target_gmv * 100) if target_gmv > 0 else 0
        
        history.append({
            "period": period_str,
            "gmv": round(gmv, 2),
            "target": round(target_gmv, 2),
            "progress": round(progress, 1)
        })
    
    return ResponseModel(data={
        "dimension": dimension,
        "history": history
    })


@router.get("/forecast", response_model=ResponseModel)
def get_pace_forecast(
    dimension: str = Query("monthly", description="时间维度"),
    db: Session = Depends(get_db)
):
    time_info = get_period_progress(dimension)
    time_progress = time_info["progress"]
    
    targets = db.query(ShopTarget).filter(
        ShopTarget.period.like(f"{datetime.now().year}%")
    ).all()
    
    target_gmv = sum(safe_float(t.target_gsv) for t in targets)
    
    if dimension == "yearly":
        Model = MonthlyData
        date_col = 'month'
    else:
        Model, date_col, _ = get_data_model(dimension)
    
    current_gmv = safe_float(db.query(func.sum(Model.payment_amount)).scalar() or 0)
    
    if time_progress > 0:
        projected_gmv = (current_gmv / time_progress) * 100
    else:
        projected_gmv = current_gmv
    
    achievement_rate = (projected_gmv / target_gmv * 100) if target_gmv > 0 else 0
    
    if achievement_rate >= 100:
        forecast_status = "achieve"
        forecast_level = "success"
        forecast_message = f"预计可达成目标 {achievement_rate:.0f}%"
    elif achievement_rate >= 90:
        forecast_status = "close"
        forecast_level = "warning"
        forecast_message = f"预计接近目标 {achievement_rate:.0f}%，需要小幅加速"
    else:
        forecast_status = "miss"
        forecast_level = "danger"
        forecast_message = f"预计无法达成目标，缺口 {target_gmv - projected_gmv:.0f} 元"
    
    return ResponseModel(data={
        "dimension": dimension,
        "time_progress": time_info,
        "current_gmv": round(current_gmv, 2),
        "target_gmv": round(target_gmv, 2),
        "projected_gmv": round(projected_gmv, 2),
        "achievement_rate": round(achievement_rate, 1),
        "gap": round(target_gmv - projected_gmv, 2),
        "forecast_status": forecast_status,
        "forecast_level": forecast_level,
        "forecast_message": forecast_message
    })
