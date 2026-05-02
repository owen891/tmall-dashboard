from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.core.utils import get_data_model, get_prev_period, get_latest_period, calculate_change, safe_float
from app.models import DailyData, WeeklyData, MonthlyData, Product, Alert
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/kpi", tags=["KPI分析"])


@router.get("", response_model=ResponseModel)
def get_kpi(
    dim: str = Query("weekly", alias="dim", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    prev_period: Optional[str] = Query(None, description="上一周期"),
    db: Session = Depends(get_db)
):
    """获取KPI数据（兼容老版本）"""
    
    dimension = dim
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"kpi": {}, "trends": []})
    
    if not prev_period:
        prev_period = get_prev_period(str(period), dimension)
    
    curr_data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == period).first()
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == prev_period).first()
    
    curr_payment = safe_float(curr_data.payment) if curr_data else 0
    prev_payment = safe_float(prev_data.payment) if prev_data else 0
    curr_visitors = safe_float(curr_data.visitors) if curr_data else 0
    prev_visitors = safe_float(prev_data.visitors) if prev_data else 0
    curr_conversion = safe_float(curr_data.conversion) if curr_data else 0
    prev_conversion = safe_float(prev_data.conversion) if prev_data else 0
    curr_ad_spend = safe_float(curr_data.ad_spend) if curr_data else 0
    prev_ad_spend = safe_float(prev_data.ad_spend) if prev_data else 0
    
    payment_change = calculate_change(curr_payment, prev_payment)
    visitors_change = calculate_change(curr_visitors, prev_visitors)
    conversion_change = calculate_change(curr_conversion, prev_conversion)
    
    roi = (curr_payment / curr_ad_spend) if curr_ad_spend > 0 else 0
    prev_roi = (prev_payment / prev_ad_spend) if prev_ad_spend > 0 else 0
    roi_change = calculate_change(roi, prev_roi)
    
    refund_rate = (curr_data.refund / curr_payment * 100) if curr_payment > 0 else 0
    prev_refund_rate = (prev_data.refund / prev_payment * 100) if prev_payment > 0 else 0
    refund_change = calculate_change(refund_rate, prev_refund_rate)
    
    kpi = {
        "total_gmv": {"value": round(curr_payment, 2), **payment_change},
        "visitors": {"value": int(curr_visitors), **visitors_change},
        "conversion": {"value": round(curr_conversion * 100, 2), **conversion_change},
        "roi": {"value": round(roi, 2), **roi_change},
        "refund_rate": {"value": round(refund_rate, 2), **refund_change},
        "ad_spend": {"value": round(curr_ad_spend, 2)},
    }
    
    return ResponseModel(data={
        "kpi": kpi,
        "dimension": dimension,
        "period": str(period),
        "prev_period": str(prev_period)
    })


@router.get("/summary", response_model=ResponseModel)
def get_kpi_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取KPI汇总（新版前端用）"""
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"kpi": {}, "dimension": dimension})
    
    prev_period = get_prev_period(str(period), dimension)
    
    data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == period).first()
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == prev_period).first()
    
    curr_payment = safe_float(data.payment) if data else 0
    prev_payment = safe_float(prev_data.payment) if prev_data else 0
    curr_visitors = safe_float(data.visitors) if data else 0
    prev_visitors = safe_float(prev_data.visitors) if prev_data else 0
    curr_conversion = safe_float(data.conversion) if data else 0
    prev_conversion = safe_float(prev_data.conversion) if prev_data else 0
    curr_ad_spend = safe_float(data.ad_spend) if data else 0
    prev_ad_spend = safe_float(prev_data.ad_spend) if prev_data else 0
    curr_refund = safe_float(data.refund) if data else 0
    
    net_sales = curr_payment - curr_refund
    roi = (net_sales / curr_ad_spend * 100) if curr_ad_spend > 0 else 0
    prev_roi = ((prev_payment - safe_float(prev_data.refund)) / prev_ad_spend * 100) if prev_ad_spend > 0 else 0
    
    kpi = {
        "total_gmv": {
            "value": round(curr_payment, 2),
            "change": round(curr_payment - prev_payment, 2),
            "change_percent": round((curr_payment - prev_payment) / prev_payment * 100, 1) if prev_payment > 0 else 0
        },
        "visitors": {
            "value": int(curr_visitors),
            "change": int(curr_visitors - prev_visitors),
            "change_percent": round((curr_visitors - prev_visitors) / prev_visitors * 100, 1) if prev_visitors > 0 else 0
        },
        "conversion": {
            "value": round(curr_conversion * 100, 2),
            "change": round((curr_conversion - prev_conversion) * 100, 2),
            "change_percent": round((curr_conversion - prev_conversion) / prev_conversion * 100, 1) if prev_conversion > 0 else 0
        },
        "roi": {
            "value": round(roi, 2),
            "change": round(roi - prev_roi, 2),
            "change_percent": round((roi - prev_roi) / prev_roi * 100, 1) if prev_roi > 0 else 0
        },
        "ad_spend": {
            "value": round(curr_ad_spend, 2),
            "change": round(curr_ad_spend - prev_ad_spend, 2),
            "change_percent": round((curr_ad_spend - prev_ad_spend) / prev_ad_spend * 100, 1) if prev_ad_spend > 0 else 0
        },
        "net_sales": {
            "value": round(net_sales, 2)
        }
    }
    
    return ResponseModel(data={
        "kpi": kpi,
        "dimension": dimension,
        "period": str(period),
        "prev_period": str(prev_period)
    })


@router.get("/dimensions", response_model=ResponseModel)
def get_kpi_dimensions(db: Session = Depends(get_db)):
    """获取可用的时间维度及其最新数据"""
    dimensions = []
    
    for dim in ['daily', 'weekly', 'monthly']:
        Model, date_col, visitors_col = get_data_model(dim)
        latest = get_latest_period(Model, date_col, db)
        
        count = 0
        if latest:
            count = db.query(Model).filter(getattr(Model, date_col) == latest).count()
        
        dimensions.append({
            "value": dim,
            "label": {"daily": "按日", "weekly": "按周", "monthly": "按月"}[dim],
            "latest_period": latest,
            "data_count": count
        })
    
    return ResponseModel(data={"dimensions": dimensions})
