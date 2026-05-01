from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/compare", tags=["竞品对比"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def get_prev_period(period_str: str, dim: str, weeks: int = 1) -> str:
    """获取上一个周期"""
    try:
        if dim == 'monthly':
            y, m = period_str.split('-')
            m = int(m) - weeks
            while m <= 0:
                m += 12
                y = str(int(y) - 1)
            return f"{y}-{m:02d}"
        else:
            d = datetime.strptime(period_str, '%Y-%m-%d')
            prev = d - timedelta(days=7 * weeks)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period_str


def get_latest_period(Model, date_col, db):
    """获取最新周期"""
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        return getattr(latest, date_col)
    return None


@router.get("/periods", response_model=ResponseModel)
def get_compare_periods(
    dimension: str = Query("weekly", description="时间维度"),
    db: Session = Depends(get_db)
):
    """获取可对比的周期列表"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    periods = db.query(getattr(Model, date_col)).distinct().order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    period_list = []
    for p in periods:
        period_str = p[0]
        if hasattr(period_str, 'isoformat'):
            period_str = period_str.isoformat()
        else:
            period_str = str(period_str)
        
        prev_period = get_prev_period(period_str, dimension)
        period_list.append({
            "period": period_str,
            "prev_period": prev_period
        })
    
    return ResponseModel(data={"periods": period_list})


@router.get("/overview", response_model=ResponseModel)
def get_compare_overview(
    product_ids: str = Query(..., description="商品ID列表，逗号分隔"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取竞品对比概览"""
    
    product_id_list = [p.strip() for p in product_ids.split(',') if p.strip()]
    
    if not product_id_list:
        return ResponseModel(data={"products": [], "metrics": {}})
    
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
        return ResponseModel(data={"products": [], "metrics": {}})
    
    prev_period = get_prev_period(str(period), dimension)
    
    products_data = db.query(
        Model.product_id,
        Model.product_name,
        Model.category,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).filter(
        getattr(Model, date_col) == period,
        Model.product_id.in_(product_id_list)
    ).group_by(
        Model.product_id,
        Model.product_name,
        Model.category
    ).all()
    
    prev_data_map = {}
    if prev_period:
        prev_query = db.query(
            Model.product_id,
            func.sum(Model.payment_amount).label('prev_payment'),
            func.sum(getattr(Model, visitors_col)).label('prev_visitors'),
        ).filter(
            getattr(Model, date_col) == prev_period,
            Model.product_id.in_(product_id_list)
        ).group_by(Model.product_id).all()
        
        prev_data_map = {p.product_id: {'payment': float(p.prev_payment or 0), 'visitors': int(p.prev_visitors or 0)} for p in prev_query}
    
    products = []
    for p in products_data:
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        prev_data = prev_data_map.get(p.product_id, {'payment': 0, 'visitors': 0})
        prev_payment = prev_data['payment']
        prev_visitors = prev_data['visitors']
        
        gmv_growth = ((payment - prev_payment) / prev_payment * 100) if prev_payment > 0 else 0
        visitors_growth = ((visitors - prev_visitors) / prev_visitors * 100) if prev_visitors > 0 else 0
        
        products.append({
            "product_id": p.product_id,
            "product_name": p.product_name,
            "category": p.category,
            "payment_amount": round(payment, 2),
            "net_sales": round(payment - refund, 2),
            "refund_rate": round((refund / payment * 100), 2) if payment > 0 else 0,
            "visitors": visitors,
            "aov": round((payment / visitors), 2) if visitors > 0 else 0,
            "conversion": round(float(p.conversion or 0) * 100, 2) if p.conversion else 0,
            "ad_spend": round(float(p.ad_spend or 0), 2),
            "roi": round(float(p.roi or 0), 2) if p.roi else 0,
            "gmv_growth": round(gmv_growth, 1),
            "visitors_growth": round(visitors_growth, 1),
        })
    
    return ResponseModel(data={
        "products": products,
        "period": str(period),
        "prev_period": str(prev_period),
        "dimension": dimension
    })


@router.get("/metrics", response_model=ResponseModel)
def get_compare_metrics(
    product_ids: str = Query(..., description="商品ID列表，逗号分隔"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    metric: str = Query("payment_amount", description="对比指标"),
    db: Session = Depends(get_db)
):
    """获取指定指标的竞品对比"""
    
    product_id_list = [p.strip() for p in product_ids.split(',') if p.strip()]
    
    if not product_id_list:
        return ResponseModel(data={"comparison": []})
    
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
        return ResponseModel(data={"comparison": []})
    
    metric_map = {
        'payment_amount': func.sum(Model.payment_amount),
        'net_sales': func.sum(Model.payment_amount) - func.sum(Model.refund_amount),
        'visitors': func.sum(getattr(Model, visitors_col)),
        'conversion': func.avg(Model.payment_conversion),
        'roi': func.avg(Model.ad_roi),
        'refund_rate': func.sum(Model.refund_amount) / func.nullif(func.sum(Model.payment_amount), 0),
        'aov': func.sum(Model.payment_amount) / func.nullif(func.sum(getattr(Model, visitors_col)), 0),
        'ad_spend': func.sum(Model.ad_spend),
    }
    
    metric_func = metric_map.get(metric, metric_map['payment_amount'])
    
    data = db.query(
        Model.product_id,
        Model.product_name,
        metric_func.label('metric_value')
    ).filter(
        getattr(Model, date_col) == period,
        Model.product_id.in_(product_id_list)
    ).group_by(
        Model.product_id,
        Model.product_name
    ).order_by(desc('metric_value')).all()
    
    comparison = []
    for i, d in enumerate(data, 1):
        value = float(d.metric_value or 0)
        if metric == 'refund_rate':
            value = value * 100
        if metric == 'conversion':
            value = value * 100
        
        comparison.append({
            "rank": i,
            "product_id": d.product_id,
            "product_name": d.product_name,
            "metric": metric,
            "value": round(value, 2)
        })
    
    return ResponseModel(data={
        "comparison": comparison,
        "metric": metric,
        "period": str(period),
        "dimension": dimension
    })


@router.get("/trend", response_model=ResponseModel)
def get_compare_trend(
    product_ids: str = Query(..., description="商品ID列表，逗号分隔"),
    dimension: str = Query("weekly", description="时间维度"),
    metric: str = Query("payment_amount", description="趋势指标"),
    periods: int = Query(8, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取竞品趋势对比"""
    
    product_id_list = [p.strip() for p in product_ids.split(',') if p.strip()]
    
    if not product_id_list:
        return ResponseModel(data={"trends": {}})
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    latest = get_latest_period(Model, date_col, db)
    if not latest:
        return ResponseModel(data={"trends": {}})
    
    latest_str = str(latest)
    period_list = [latest_str]
    for _ in range(periods - 1):
        prev = get_prev_period(period_list[-1], dimension)
        period_list.append(prev)
    
    period_list.reverse()
    
    metric_map = {
        'payment_amount': func.sum(Model.payment_amount),
        'net_sales': func.sum(Model.payment_amount) - func.sum(Model.refund_amount),
        'visitors': func.sum(getattr(Model, visitors_col)),
        'conversion': func.avg(Model.payment_conversion),
        'roi': func.avg(Model.ad_roi),
        'refund_rate': func.sum(Model.refund_amount) / func.nullif(func.sum(Model.payment_amount), 0),
        'aov': func.sum(Model.payment_amount) / func.nullif(func.sum(getattr(Model, visitors_col)), 0),
        'ad_spend': func.sum(Model.ad_spend),
    }
    
    metric_func = metric_map.get(metric, metric_map['payment_amount'])
    
    trends = {pid: {"product_name": "", "data": []} for pid in product_id_list}
    
    for period in period_list:
        data = db.query(
            Model.product_id,
            Model.product_name,
            metric_func.label('metric_value')
        ).filter(
            getattr(Model, date_col) == period,
            Model.product_id.in_(product_id_list)
        ).group_by(
            Model.product_id,
            Model.product_name
        ).all()
        
        for d in data:
            value = float(d.metric_value or 0)
            if metric in ['refund_rate', 'conversion']:
                value = value * 100
            
            if d.product_id not in trends:
                trends[d.product_id] = {"product_name": d.product_name, "data": []}
            else:
                trends[d.product_id]["product_name"] = d.product_name
            
            trends[d.product_id]["data"].append({
                "period": period,
                "value": round(value, 2)
            })
    
    for pid in product_id_list:
        if trends[pid]["product_name"] == "":
            product = db.query(Product).filter(Product.product_id == pid).first()
            if product:
                trends[pid]["product_name"] = product.product_name or pid
    
    return ResponseModel(data={
        "trends": trends,
        "metric": metric,
        "periods": period_list,
        "dimension": dimension
    })


@router.get("/category", response_model=ResponseModel)
def get_category_comparison(
    product_ids: str = Query(..., description="商品ID列表，逗号分隔"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取类目内竞品对比"""
    
    product_id_list = [p.strip() for p in product_ids.split(',') if p.strip()]
    
    if not product_id_list:
        return ResponseModel(data={"rankings": []})
    
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
        return ResponseModel(data={"rankings": []})
    
    target_products = db.query(
        Model.product_id,
        Model.product_name,
        Model.category
    ).filter(
        getattr(Model, date_col) == period,
        Model.product_id.in_(product_id_list)
    ).group_by(
        Model.product_id,
        Model.product_name,
        Model.category
    ).all()
    
    if not target_products:
        return ResponseModel(data={"rankings": []})
    
    target_categories = [p.category for p in target_products if p.category]
    target_ids = [p.product_id for p in target_products]
    
    rankings = []
    
    for product in target_products:
        category = product.category
        if not category:
            continue
        
        category_products = db.query(
            Model.product_id,
            Model.product_name,
            func.sum(Model.payment_amount).label('payment_amount'),
        ).filter(
            getattr(Model, date_col) == period,
            Model.category == category,
            Model.product_id != product.product_id
        ).group_by(
            Model.product_id,
            Model.product_name
        ).order_by(desc(func.sum(Model.payment_amount))).limit(5).all()
        
        rank = 1
        for cp in category_products:
            if cp.product_id in target_ids:
                break
            rank += 1
        
        ranking = {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "category": category,
            "rank_in_category": rank,
            "competitors": [
                {
                    "product_id": cp.product_id,
                    "product_name": cp.product_name,
                    "payment_amount": round(float(cp.payment_amount or 0), 2)
                }
                for cp in category_products[:5]
            ]
        }
        
        rankings.append(ranking)
    
    return ResponseModel(data={
        "rankings": rankings,
        "period": str(period),
        "dimension": dimension
    })


@router.get("/summary", response_model=ResponseModel)
def get_compare_summary(
    product_ids: str = Query(..., description="商品ID列表，逗号分隔"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取竞品对比汇总"""
    
    product_id_list = [p.strip() for p in product_ids.split(',') if p.strip()]
    
    if not product_id_list:
        return ResponseModel(data={"summary": {}, "products": []})
    
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
        return ResponseModel(data={"summary": {}, "products": []})
    
    prev_period = get_prev_period(str(period), dimension)
    
    products_data = db.query(
        Model.product_id,
        Model.product_name,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).filter(
        getattr(Model, date_col) == period,
        Model.product_id.in_(product_id_list)
    ).group_by(
        Model.product_id,
        Model.product_name
    ).all()
    
    total_payment = sum(float(p.payment_amount or 0) for p in products_data)
    total_visitors = sum(int(p.visitors or 0) for p in products_data)
    avg_conversion = sum(float(p.conversion or 0) for p in products_data) / len(products_data) if products_data else 0
    avg_roi = sum(float(p.roi or 0) for p in products_data if p.roi) / len([p for p in products_data if p.roi]) if any(p.roi for p in products_data) else 0
    
    summary = {
        "total_payment": round(total_payment, 2),
        "total_visitors": total_visitors,
        "avg_conversion": round(avg_conversion * 100, 2),
        "avg_roi": round(avg_roi, 2),
        "product_count": len(products_data)
    }
    
    products = []
    for p in products_data:
        payment = float(p.payment_amount or 0)
        visitors = int(p.visitors or 0)
        
        products.append({
            "product_id": p.product_id,
            "product_name": p.product_name,
            "payment_amount": round(payment, 2),
            "share": round((payment / total_payment * 100), 1) if total_payment > 0 else 0,
            "visitors": visitors,
            "conversion": round(float(p.conversion or 0) * 100, 2) if p.conversion else 0,
            "roi": round(float(p.roi or 0), 2) if p.roi else 0
        })
    
    products.sort(key=lambda x: x['payment_amount'], reverse=True)
    
    return ResponseModel(data={
        "summary": summary,
        "products": products,
        "period": str(period),
        "dimension": dimension
    })
