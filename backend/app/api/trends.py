from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.core.utils import get_data_model, get_prev_period, get_latest_period
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/trends", tags=["趋势分析"])


def calculate_trend(values: List[float]) -> dict:
    """计算趋势指标"""
    if len(values) < 2:
        return {"trend": "stable", "change": 0, "change_percent": 0}
    
    first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
    second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
    
    if first_half_avg > 0:
        change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
    else:
        change_percent = 0
    
    if change_percent > 10:
        trend = "up"
    elif change_percent < -10:
        trend = "down"
    else:
        trend = "stable"
    
    return {
        "trend": trend,
        "change": round(second_half_avg - first_half_avg, 2),
        "change_percent": round(change_percent, 1)
    }


def get_period_list(period: str, dimension: str, count: int) -> List[str]:
    """获取周期列表"""
    period_list = []
    current = str(period)
    for _ in range(count):
        period_list.append(current)
        current = get_prev_period(current, dimension)
    period_list.reverse()
    return period_list


@router.get("", response_model=ResponseModel)
def get_trends(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取趋势数据"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trends": {}, "summary": {}})
    
    period_list = get_period_list(str(period), dimension, periods)
    
    all_data = db.query(
        getattr(Model, date_col).label('period'),
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(
        getattr(Model, date_col).in_(period_list)
    ).group_by(getattr(Model, date_col)).all()
    
    trend_data = {}
    for d in all_data:
        p = str(d.period)
        trend_data[p] = {
            "payment_amount": float(d.payment or 0),
            "refund_amount": float(d.refund or 0),
            "net_sales": float(d.payment or 0) - float(d.refund or 0),
            "visitors": int(d.visitors or 0),
            "conversion": float(d.conversion or 0),
            "ad_spend": float(d.ad_spend or 0)
        }
    
    payments = [v['payment_amount'] for v in trend_data.values()]
    visitors_list = [v['visitors'] for v in trend_data.values()]
    conversions = [v['conversion'] for v in trend_data.values()]
    
    summary = {
        "payment_trend": calculate_trend(payments),
        "visitors_trend": calculate_trend(visitors_list),
        "conversion_trend": calculate_trend(conversions),
        "total_payment": sum(payments),
        "total_visitors": sum(visitors_list),
        "avg_conversion": sum(conversions) / len(conversions) if conversions else 0
    }
    
    return ResponseModel(data={
        "trends": trend_data,
        "summary": summary,
        "periods": period_list,
        "dimension": dimension
    })


@router.get("/overview", response_model=ResponseModel)
def get_trends_overview(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取趋势概览"""
    return get_trends(dimension, period, periods, db)


@router.get("/payment", response_model=ResponseModel)
def get_payment_trend(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取支付金额趋势"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trend": []})
    
    period_list = get_period_list(str(period), dimension, periods)
    
    all_data = db.query(
        getattr(Model, date_col).label('period'),
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
    ).filter(
        getattr(Model, date_col).in_(period_list)
    ).group_by(getattr(Model, date_col)).all()
    
    data_map = {str(d.period): d for d in all_data}
    
    trend = []
    for p in period_list:
        data = data_map.get(p)
        payment = float(data.payment or 0) if data else 0
        refund = float(data.refund or 0) if data else 0
        
        trend.append({
            "period": p,
            "payment_amount": round(payment, 2),
            "refund_amount": round(refund, 2),
            "net_sales": round(payment - refund, 2)
        })
    
    return ResponseModel(data={
        "trend": trend,
        "periods": period_list,
        "dimension": dimension
    })


@router.get("/visitors", response_model=ResponseModel)
def get_visitors_trend(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取访客趋势"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trend": []})
    
    period_list = get_period_list(str(period), dimension, periods)
    
    all_data = db.query(
        getattr(Model, date_col).label('period'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.sum(Model.payment_amount).label('payment'),
    ).filter(
        getattr(Model, date_col).in_(period_list)
    ).group_by(getattr(Model, date_col)).all()
    
    data_map = {str(d.period): d for d in all_data}
    
    trend = []
    for p in period_list:
        data = data_map.get(p)
        visitors = int(data.visitors or 0) if data else 0
        payment = float(data.payment or 0) if data else 0
        
        trend.append({
            "period": p,
            "visitors": visitors,
            "uv_value": round(payment / visitors, 2) if visitors > 0 else 0
        })
    
    return ResponseModel(data={
        "trend": trend,
        "periods": period_list,
        "dimension": dimension
    })


@router.get("/conversion", response_model=ResponseModel)
def get_conversion_trend(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取转化率趋势"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trend": []})
    
    period_list = get_period_list(str(period), dimension, periods)
    
    all_data = db.query(
        getattr(Model, date_col).label('period'),
        func.avg(Model.payment_conversion).label('conversion'),
    ).filter(
        getattr(Model, date_col).in_(period_list)
    ).group_by(getattr(Model, date_col)).all()
    
    data_map = {str(d.period): d for d in all_data}
    
    trend = []
    for p in period_list:
        data = data_map.get(p)
        conversion = float(data.conversion or 0) if data else 0
        
        trend.append({
            "period": p,
            "conversion": round(conversion * 100, 2)
        })
    
    return ResponseModel(data={
        "trend": trend,
        "periods": period_list,
        "dimension": dimension
    })


@router.get("/product/{product_id}", response_model=ResponseModel)
def get_product_trend(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取单个商品的趋势"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    data_points = db.query(Model).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(periods).all()
    
    if not data_points:
        return ResponseModel(data={"trend": []})
    
    trend = []
    for d in reversed(data_points):
        period_val = getattr(d, date_col)
        if hasattr(period_val, 'isoformat'):
            period_str = period_val.isoformat()
        else:
            period_str = str(period_val)
        
        payment = d.payment_amount or 0
        refund = d.refund_amount or 0
        visitors = getattr(d, visitors_col) or 0
        
        trend.append({
            "period": period_str,
            "payment_amount": round(payment, 2),
            "refund_amount": round(refund, 2),
            "net_sales": round(payment - refund, 2),
            "visitors": visitors,
            "conversion": round(float(d.payment_conversion or 0) * 100, 2),
            "ad_spend": round(float(d.ad_spend or 0), 2),
            "roi": round(float(d.ad_roi or 0), 2) if d.ad_roi else 0
        })
    
    payments = [t['payment_amount'] for t in trend]
    visitors_list = [t['visitors'] for t in trend]
    
    return ResponseModel(data={
        "product_id": product_id,
        "trend": trend,
        "summary": {
            "payment_trend": calculate_trend(payments),
            "visitors_trend": calculate_trend(visitors_list)
        },
        "dimension": dimension
    })
