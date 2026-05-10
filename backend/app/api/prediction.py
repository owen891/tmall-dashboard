from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.models import Product, WeeklyData, MonthlyData, DailyData
import math

router = APIRouter(prefix="/prediction", tags=["预测分析"])


@router.get("/overview", response_model=ResponseModel)
def get_prediction_overview(
    periods: int = Query(4, ge=1, le=12, description="预测周期数"),
    db: Session = Depends(get_db)
):
    gmv_data = db.query(
        func.avg(WeeklyData.payment_amount).label('avg_gmv'),
    ).first()
    avg_gmv = float(gmv_data.avg_gmv or 0) if gmv_data else 0

    predictions = []
    current = avg_gmv
    for i in range(1, periods + 1):
        growth = 1 + (0.02 * (i % 3 - 1))
        current = current * growth
        predictions.append({
            "period": f"W+{i}",
            "predicted_gmv": round(current, 2),
            "confidence": round(max(0.6, 0.95 - i * 0.05), 2),
            "trend": "up" if growth > 1 else "down"
        })

    return ResponseModel(data={
        "dimension": "weekly",
        "predictions": predictions,
        "avg_gmv": round(avg_gmv, 2),
        "trend": "stable",
        "confidence": 0.85
    })


@router.get("/gmv", response_model=ResponseModel)
def predict_gmv(
    periods: int = Query(4, ge=1, le=12, description="预测周期数"),
    db: Session = Depends(get_db)
):
    """
    GMV 预测
    基于历史数据使用简单线性回归预测未来
    """
    weekly_data = db.query(
        WeeklyData.week_start,
        func.sum(WeeklyData.payment_amount).label('gmv')
    ).group_by(WeeklyData.week_start).order_by(WeeklyData.week_start).limit(12).all()
    
    if len(weekly_data) < 3:
        return ResponseModel(data={
            "prediction": [],
            "confidence": 0,
            "message": "数据不足，无法预测"
        })
    
    values = [d.gmv for d in weekly_data]
    n = len(values)
    
    x_mean = sum(range(n)) / n
    y_mean = sum(values) / n
    
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        slope = 0
    else:
        slope = numerator / denominator
    
    intercept = y_mean - slope * x_mean
    
    predictions = []
    for i in range(periods):
        pred_x = n + i
        pred_value = slope * pred_x + intercept
        lower = pred_value * 0.85
        upper = pred_value * 1.15
        
        week_offset = i + 1
        pred_date = datetime.now() + timedelta(weeks=week_offset)
        
        predictions.append({
            "period": i + 1,
            "date": pred_date.strftime("%Y-%m-%d"),
            "predicted_gmv": round(max(0, pred_value), 2),
            "lower_bound": round(max(0, lower), 2),
            "upper_bound": round(max(0, upper), 2),
            "trend": "up" if slope > 0 else "down"
        })
    
    r_squared = calculate_r_squared(values, slope, intercept, x_mean, y_mean)
    
    return ResponseModel(data={
        "predictions": predictions,
        "confidence": round(r_squared * 100, 1),
        "trend": "up" if slope > 0 else "down",
        "avg_weekly_gmv": round(sum(values) / len(values), 2)
    })


@router.get("/sales", response_model=ResponseModel)
def predict_sales(
    product_id: Optional[str] = Query(None, description="商品ID，不传则预测整体"),
    periods: int = Query(4, ge=1, le=12, description="预测周期数"),
    db: Session = Depends(get_db)
):
    """
    销量预测
    预测未来销量趋势
    """
    if product_id:
        query = db.query(
            WeeklyData.week_start,
            WeeklyData.ipv
        ).filter(WeeklyData.product_id == product_id)
    else:
        query = db.query(
            WeeklyData.week_start,
            func.sum(WeeklyData.ipv).label('ipv')
        ).group_by(WeeklyData.week_start)
    
    sales_data = query.order_by(WeeklyData.week_start).limit(12).all()
    
    if len(sales_data) < 3:
        return ResponseModel(data={
            "predictions": [],
            "confidence": 0,
            "message": "数据不足，无法预测"
        })
    
    values = [d.ipv for d in sales_data]
    n = len(values)
    
    x_mean = sum(range(n)) / n
    y_mean = sum(values) / n
    
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean
    
    predictions = []
    for i in range(periods):
        pred_x = n + i
        pred_value = slope * pred_x + intercept
        
        week_offset = i + 1
        pred_date = datetime.now() + timedelta(weeks=week_offset)
        
        predictions.append({
            "period": i + 1,
            "date": pred_date.strftime("%Y-%m-%d"),
            "predicted_visitors": int(max(0, pred_value)),
            "growth_rate": round((pred_value - values[-1]) / values[-1] * 100, 1) if values[-1] > 0 else 0
        })
    
    r_squared = calculate_r_squared(values, slope, intercept, x_mean, y_mean)
    
    return ResponseModel(data={
        "product_id": product_id,
        "predictions": predictions,
        "confidence": round(r_squared * 100, 1),
        "avg_visitors": int(sum(values) / len(values))
    })


@router.get("/stock", response_model=ResponseModel)
def predict_stock(
    product_id: str = Query(..., description="商品ID"),
    lead_time: int = Query(7, ge=1, le=30, description="补货提前期（天）"),
    target_days: int = Query(30, ge=7, le=90, description="目标销售天数"),
    db: Session = Depends(get_db)
):
    """
    库存预测
    计算安全库存和补货点
    """
    daily_data = db.query(DailyData).filter(
        DailyData.product_id == product_id
    ).order_by(DailyData.date.desc()).limit(30).all()
    
    if len(daily_data) < 7:
        return ResponseModel(data={
            "message": "数据不足，无法预测"
        })
    
    daily_sales = [d.payment_qty for d in daily_data if d.payment_qty]
    if not daily_sales:
        daily_sales = [1]
    
    avg_daily_sales = sum(daily_sales) / len(daily_sales)
    std_dev = math.sqrt(sum((x - avg_daily_sales) ** 2 for x in daily_sales) / len(daily_sales))
    
    z_score = 1.65
    
    safety_stock = z_score * std_dev * math.sqrt(lead_time)
    
    reorder_point = (avg_daily_sales * lead_time) + safety_stock
    
    current_stock = sum(daily_sales) * 3
    
    days_until_stockout = current_stock / avg_daily_sales if avg_daily_sales > 0 else 999
    
    suggested_order_qty = (avg_daily_sales * target_days) + safety_stock - current_stock
    
    return ResponseModel(data={
        "product_id": product_id,
        "avg_daily_sales": round(avg_daily_sales, 1),
        "safety_stock": int(max(0, safety_stock)),
        "reorder_point": int(max(0, reorder_point)),
        "current_stock_estimate": int(current_stock),
        "days_until_stockout": round(days_until_stockout, 1),
        "suggested_order_qty": int(max(0, suggested_order_qty)),
        "urgency": "high" if days_until_stockout < lead_time else "medium" if days_until_stockout < lead_time * 2 else "low"
    })


@router.get("/roi", response_model=ResponseModel)
def predict_roi(
    product_id: Optional[str] = Query(None, description="商品ID"),
    periods: int = Query(4, ge=1, le=12, description="预测周期数"),
    db: Session = Depends(get_db)
):
    """
    ROI 预测
    预测广告投放效果
    """
    if product_id:
        query = db.query(
            WeeklyData.week_start,
            WeeklyData.ad_roi
        ).filter(
            WeeklyData.product_id == product_id,
            WeeklyData.ad_roi > 0
        )
    else:
        query = db.query(
            WeeklyData.week_start,
            func.avg(WeeklyData.ad_roi).label('ad_roi')
        ).filter(WeeklyData.ad_roi > 0).group_by(WeeklyData.week_start)
    
    roi_data = query.order_by(WeeklyData.week_start).limit(12).all()
    
    if len(roi_data) < 3:
        return ResponseModel(data={
            "predictions": [],
            "message": "数据不足，无法预测"
        })
    
    values = [d.ad_roi for d in roi_data if d.ad_roi and d.ad_roi > 0]
    if len(values) < 3:
        return ResponseModel(data={
            "predictions": [],
            "message": "数据不足，无法预测"
        })
    
    n = len(values)
    x_mean = sum(range(n)) / n
    y_mean = sum(values) / n
    
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean
    
    predictions = []
    for i in range(periods):
        pred_x = n + i
        pred_value = slope * pred_x + intercept
        
        week_offset = i + 1
        pred_date = datetime.now() + timedelta(weeks=week_offset)
        
        predictions.append({
            "period": i + 1,
            "date": pred_date.strftime("%Y-%m-%d"),
            "predicted_roi": round(max(0, pred_value), 2),
            "assessment": "good" if pred_value > 3 else "normal" if pred_value > 1 else "poor"
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "predictions": predictions,
        "avg_roi": round(sum(values) / len(values), 2),
        "trend": "improving" if slope > 0.1 else "stable" if slope > -0.1 else "declining"
    })


def calculate_r_squared(y_values, slope, intercept, x_mean, y_mean):
    """计算 R² 值"""
    n = len(y_values)
    ss_tot = sum((y_values[i] - y_mean) ** 2 for i in range(n))
    
    if ss_tot == 0:
        return 0
    
    ss_res = sum((y_values[i] - (slope * i + intercept)) ** 2 for i in range(n))
    
    r_squared = 1 - (ss_res / ss_tot)
    return max(0, min(1, r_squared))
