from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/trends", tags=["趋势分析"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def get_prev_period(period_str: str, dim: str) -> str:
    """获取上一个周期"""
    try:
        if dim == 'monthly':
            y, m = period_str.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        else:
            d = datetime.strptime(period_str, '%Y-%m-%d')
            if dim == 'weekly':
                prev = d - timedelta(days=7)
            else:
                prev = d - timedelta(days=1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period_str


def get_latest_period(Model, date_col, db):
    """获取最新周期"""
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        return getattr(latest, date_col)
    return None


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


@router.get("/overview", response_model=ResponseModel)
def get_trends_overview(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取趋势概览"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trends": {}, "summary": {}})
    
    period_list = []
    current = str(period)
    for _ in range(periods):
        period_list.append(current)
        current = get_prev_period(current, dimension)
    period_list.reverse()
    
    trend_data = {}
    
    for p in period_list:
        data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ).filter(getattr(Model, date_col) == p).first()
        
        if data:
            trend_data[p] = {
                "payment_amount": float(data.payment or 0),
                "refund_amount": float(data.refund or 0),
                "net_sales": float(data.payment or 0) - float(data.refund or 0),
                "visitors": int(data.visitors or 0),
                "conversion": float(data.conversion or 0),
                "ad_spend": float(data.ad_spend or 0)
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


@router.get("/payment", response_model=ResponseModel)
def get_payment_trend(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取支付金额趋势"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trend": []})
    
    period_list = []
    current = str(period)
    for _ in range(periods):
        period_list.append(current)
        current = get_prev_period(current, dimension)
    period_list.reverse()
    
    trend = []
    for p in period_list:
        data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
        ).filter(getattr(Model, date_col) == p).first()
        
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
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trend": []})
    
    period_list = []
    current = str(period)
    for _ in range(periods):
        period_list.append(current)
        current = get_prev_period(current, dimension)
    period_list.reverse()
    
    trend = []
    for p in period_list:
        data = db.query(
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.sum(Model.payment_amount).label('payment'),
        ).filter(getattr(Model, date_col) == p).first()
        
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
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trend": []})
    
    period_list = []
    current = str(period)
    for _ in range(periods):
        period_list.append(current)
        current = get_prev_period(current, dimension)
    period_list.reverse()
    
    trend = []
    for p in period_list:
        data = db.query(
            func.avg(Model.payment_conversion).label('conversion'),
        ).filter(getattr(Model, date_col) == p).first()
        
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


@router.get("/category", response_model=ResponseModel)
def get_category_trend(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取类目趋势"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"trends": {}})
    
    categories = db.query(Model.category).filter(
        getattr(Model, date_col) == period,
        Model.category.isnot(None)
    ).distinct().all()
    
    category_list = [c[0] for c in categories if c[0]]
    
    period_list = []
    current = str(period)
    for _ in range(periods):
        period_list.append(current)
        current = get_prev_period(current, dimension)
    period_list.reverse()
    
    trends = {}
    
    for cat in category_list:
        cat_trend = []
        for p in period_list:
            data = db.query(
                func.sum(Model.payment_amount).label('payment'),
            ).filter(
                getattr(Model, date_col) == p,
                Model.category == cat
            ).first()
            
            payment = float(data.payment or 0) if data else 0
            cat_trend.append({
                "period": p,
                "payment_amount": round(payment, 2)
            })
        
        trends[cat] = cat_trend
    
    return ResponseModel(data={
        "trends": trends,
        "categories": category_list,
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
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
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
