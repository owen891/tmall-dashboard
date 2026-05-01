from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


def get_prev_period(period_str: str, dim: str) -> str:
    """获取上一个周期"""
    from datetime import datetime, timedelta
    
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


@router.get("", response_model=ResponseModel)
def get_dashboard(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取仪表盘汇总数据（兼容老版本）"""
    
    if dimension == "monthly":
        Model = MonthlyData
        date_col = 'month'
        visitors_col = 'visitors'
    elif dimension == "daily":
        Model = DailyData
        date_col = 'date'
        visitors_col = 'ipv'
    else:
        Model = WeeklyData
        date_col = 'week_start'
        visitors_col = 'ipv'
    
    if not period:
        latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
        period = getattr(latest, date_col) if latest else None
    
    if not period:
        return ResponseModel(data={
            "summary": {},
            "trends": [],
            "top_products": [],
            "category_distribution": [],
            "period": None,
            "prev_period": None
        })
    
    period_str = str(period)
    prev_period_str = get_prev_period(period_str, dimension)
    
    summary_query = db.query(
        func.sum(Model.payment_amount).label('total_payment'),
        func.sum(Model.refund_amount).label('total_refund'),
        func.sum(getattr(Model, visitors_col)).label('total_visitors'),
        func.sum(Model.ad_spend).label('total_ad_spend'),
        func.avg(Model.payment_conversion).label('avg_conversion'),
        func.avg(Model.ad_roi).label('avg_roi'),
        func.count(func.distinct(Model.product_id)).label('product_count')
    ).filter(getattr(Model, date_col) == period).first()
    
    prev_summary_query = db.query(
        func.sum(Model.payment_amount).label('total_payment'),
        func.sum(Model.refund_amount).label('total_refund'),
        func.sum(getattr(Model, visitors_col)).label('total_visitors'),
        func.sum(Model.ad_spend).label('total_ad_spend'),
        func.avg(Model.payment_conversion).label('avg_conversion'),
        func.avg(Model.ad_roi).label('avg_roi'),
    ).filter(getattr(Model, date_col) == prev_period_str).first()
    
    total_payment = float(summary_query.total_payment or 0) if summary_query else 0
    total_refund = float(summary_query.total_refund or 0) if summary_query else 0
    total_visitors = int(summary_query.total_visitors or 0) if summary_query else 0
    total_ad_spend = float(summary_query.total_ad_spend or 0) if summary_query else 0
    avg_conversion = float(summary_query.avg_conversion or 0) if summary_query else 0
    avg_roi = float(summary_query.avg_roi or 0) if summary_query and summary_query.avg_roi else 0
    product_count = int(summary_query.product_count or 0) if summary_query else 0
    
    prev_payment = float(prev_summary_query.total_payment or 0) if prev_summary_query else 0
    prev_visitors = int(prev_summary_query.total_visitors or 0) if prev_summary_query else 0
    prev_conversion = float(prev_summary_query.avg_conversion or 0) if prev_summary_query else 0
    prev_roi = float(prev_summary_query.avg_roi or 0) if prev_summary_query and prev_summary_query.avg_roi else 0
    
    net_sales = total_payment - total_refund
    refund_rate = (total_refund / total_payment * 100) if total_payment > 0 else 0
    prev_refund_rate = (float(prev_summary_query.total_refund or 0) / prev_payment * 100) if prev_payment > 0 else 0 if prev_summary_query else 0
    ad_ratio = (total_ad_spend / total_payment * 100) if total_payment > 0 else 0
    uv_value = (total_payment / total_visitors) if total_visitors > 0 else 0
    prev_uv_value = (prev_payment / prev_visitors) if prev_visitors > 0 else 0
    
    summary = {
        "total_payment": {
            "value": round(total_payment, 2),
            "prev_value": round(prev_payment, 2),
            "change": round(((total_payment - prev_payment) / prev_payment * 100), 1) if prev_payment > 0 else 0,
            "label": "总GMV"
        },
        "net_sales": {
            "value": round(net_sales, 2),
            "change": round(((net_sales - (prev_payment - float(prev_summary_query.total_refund or 0) if prev_summary_query else 0)) / (prev_payment - float(prev_summary_query.total_refund or 0) if prev_summary_query else 1)) * 100, 1) if (prev_payment - float(prev_summary_query.total_refund or 0) if prev_summary_query else 0) > 0 else 0,
            "label": "净销售额"
        },
        "total_visitors": {
            "value": total_visitors,
            "prev_value": prev_visitors,
            "change": round(((total_visitors - prev_visitors) / prev_visitors * 100), 1) if prev_visitors > 0 else 0,
            "label": "总访客"
        },
        "uv_value": {
            "value": round(uv_value, 2),
            "prev_value": round(prev_uv_value, 2),
            "change": round(((uv_value - prev_uv_value) / prev_uv_value * 100), 1) if prev_uv_value > 0 else 0,
            "label": "UV价值"
        },
        "avg_conversion": {
            "value": round(avg_conversion * 100, 2) if avg_conversion < 1 else round(avg_conversion, 2),
            "prev_value": round(prev_conversion * 100, 2) if prev_conversion < 1 else round(prev_conversion, 2),
            "change": round(((avg_conversion - prev_conversion) / prev_conversion * 100), 1) if prev_conversion > 0 else 0,
            "label": "平均转化率",
            "unit": "%"
        },
        "avg_roi": {
            "value": round(avg_roi, 2),
            "prev_value": round(prev_roi, 2),
            "change": round(((avg_roi - prev_roi) / prev_roi * 100), 1) if prev_roi > 0 else 0,
            "label": "平均ROI"
        },
        "total_refund": {
            "value": round(total_refund, 2),
            "label": "总退款"
        },
        "refund_rate": {
            "value": round(refund_rate, 2),
            "prev_value": round(prev_refund_rate, 2),
            "change": round(refund_rate - prev_refund_rate, 2),
            "label": "退款率",
            "unit": "%"
        },
        "ad_spend": {
            "value": round(total_ad_spend, 2),
            "label": "广告支出"
        },
        "ad_ratio": {
            "value": round(ad_ratio, 2),
            "label": "广告占比",
            "unit": "%"
        },
        "product_count": {
            "value": product_count,
            "label": "商品数量"
        }
    }
    
    top_products_query = db.query(
        Model.product_id,
        Model.product_name,
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).filter(
        getattr(Model, date_col) == period
    ).group_by(
        Model.product_id,
        Model.product_name
    ).order_by(desc(func.sum(Model.payment_amount))).limit(10).all()
    
    top_products = []
    for p in top_products_query:
        payment = float(p.payment or 0)
        refund = float(p.refund or 0)
        visitors = int(p.visitors or 0)
        ad_spend = float(p.ad_spend or 0)
        
        top_products.append({
            "product_id": p.product_id,
            "product_name": p.product_name,
            "payment_amount": round(payment, 2),
            "net_sales": round(payment - refund, 2),
            "refund_amount": round(refund, 2),
            "refund_rate": round((refund / payment * 100), 2) if payment > 0 else 0,
            "visitors": visitors,
            "conversion": round(float(p.conversion or 0) * 100, 2) if p.conversion else 0,
            "ad_spend": round(ad_spend, 2),
            "roi": round(float(p.roi or 0), 2) if p.roi else 0,
            "ad_ratio": round((ad_spend / payment * 100), 2) if payment > 0 else 0
        })
    
    category_query = db.query(
        Model.category,
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.payment_amount).label('value')
    ).filter(
        getattr(Model, date_col) == period,
        Model.category.isnot(None)
    ).group_by(Model.category).all()
    
    category_distribution = []
    total_category_payment = sum(float(c.payment or 0) for c in category_query)
    for c in category_query:
        payment = float(c.payment or 0)
        category_distribution.append({
            "category": c.category,
            "payment": round(payment, 2),
            "value": round(payment, 2),
            "percent": round((payment / total_category_payment * 100), 1) if total_category_payment > 0 else 0
        })
    
    trends_query = db.query(
        getattr(Model, date_col).label('period'),
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
    ).group_by(getattr(Model, date_col)).order_by(getattr(Model, date_col)).limit(12).all()
    
    trends = []
    for t in trends_query:
        payment = float(t.payment or 0)
        refund = float(t.refund or 0)
        visitors = int(t.visitors or 0)
        period_val = t.period
        
        if hasattr(period_val, 'isoformat'):
            period_str = period_val.isoformat()
        else:
            period_str = str(period_val)
        
        trends.append({
            "period": period_str,
            "payment_amount": round(payment, 2),
            "net_sales": round(payment - refund, 2),
            "visitors": visitors,
            "conversion": round(float(t.conversion or 0) * 100, 2) if t.conversion else 0
        })
    
    return ResponseModel(data={
        "summary": summary,
        "trends": trends,
        "top_products": top_products,
        "category_distribution": category_distribution,
        "period": period_str,
        "prev_period": prev_period_str,
        "dimension": dimension
    })


@router.get("/summary", response_model=ResponseModel)
def get_dashboard_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取仪表盘汇总数据（新版前端用）"""
    
    if dimension == "monthly":
        Model = MonthlyData
        date_col = 'month'
        visitors_col = 'visitors'
    elif dimension == "daily":
        Model = DailyData
        date_col = 'date'
        visitors_col = 'ipv'
    else:
        Model = WeeklyData
        date_col = 'week_start'
        visitors_col = 'ipv'
    
    if not period:
        latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
        period = getattr(latest, date_col) if latest else None
    
    if not period:
        return ResponseModel(data={"kpi": {}, "trends": []})
    
    period_str = str(period)
    prev_period_str = get_prev_period(period_str, dimension)
    
    current_data = db.query(
        func.sum(Model.payment_amount).label('total_payment'),
        func.sum(Model.refund_amount).label('total_refund'),
        func.sum(getattr(Model, visitors_col)).label('total_visitors'),
        func.sum(Model.ad_spend).label('total_ad_spend'),
        func.avg(Model.payment_conversion).label('avg_conversion'),
        func.avg(Model.ad_roi).label('avg_roi'),
    ).filter(getattr(Model, date_col) == period).first()
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('total_payment'),
        func.sum(Model.refund_amount).label('total_refund'),
        func.sum(getattr(Model, visitors_col)).label('total_visitors'),
        func.avg(Model.payment_conversion).label('avg_conversion'),
        func.avg(Model.ad_roi).label('avg_roi'),
    ).filter(getattr(Model, date_col) == prev_period_str).first()
    
    if not current_data:
        return ResponseModel(data={"kpi": {}, "trends": []})
    
    total_payment = float(current_data.total_payment or 0)
    total_refund = float(current_data.total_refund or 0)
    total_visitors = int(current_data.total_visitors or 0)
    total_ad_spend = float(current_data.total_ad_spend or 0)
    avg_conversion = float(current_data.avg_conversion or 0)
    avg_roi = float(current_data.avg_roi or 0) if current_data.avg_roi else 0
    
    prev_payment = float(prev_data.total_payment or 0) if prev_data else 0
    prev_visitors = int(prev_data.total_visitors or 0) if prev_data else 0
    prev_conversion = float(prev_data.avg_conversion or 0) if prev_data else 0
    prev_roi = float(prev_data.avg_roi or 0) if prev_data and prev_data.avg_roi else 0
    
    net_sales = total_payment - total_refund
    refund_rate = (total_refund / total_payment * 100) if total_payment > 0 else 0
    uv_value = (total_payment / total_visitors) if total_visitors > 0 else 0
    
    kpi = {
        "total_gmv": {
            "value": round(total_payment, 2),
            "change": round(((total_payment - prev_payment) / prev_payment * 100), 1) if prev_payment > 0 else 0,
            "label": "总GMV"
        },
        "net_sales": {
            "value": round(net_sales, 2),
            "label": "净销售额"
        },
        "visitors": {
            "value": total_visitors,
            "change": round(((total_visitors - prev_visitors) / prev_visitors * 100), 1) if prev_visitors > 0 else 0,
            "label": "访客数"
        },
        "uv_value": {
            "value": round(uv_value, 2),
            "label": "UV价值"
        },
        "conversion": {
            "value": round(avg_conversion * 100, 2),
            "label": "转化率",
            "unit": "%"
        },
        "roi": {
            "value": round(avg_roi, 2),
            "label": "平均ROI"
        },
        "refund_rate": {
            "value": round(refund_rate, 2),
            "label": "退款率",
            "unit": "%"
        }
    }
    
    trends_query = db.query(
        getattr(Model, date_col).label('period'),
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
    ).group_by(getattr(Model, date_col)).order_by(getattr(Model, date_col)).limit(12).all()
    
    trends = []
    for t in trends_query:
        period_val = t.period
        if hasattr(period_val, 'isoformat'):
            period_str = period_val.isoformat()
        else:
            period_str = str(period_val)
        
        trends.append({
            "period": period_str,
            "payment_amount": round(float(t.payment or 0), 2),
            "net_sales": round(float(t.payment or 0) - float(t.refund or 0), 2),
            "visitors": int(t.visitors or 0)
        })
    
    return ResponseModel(data={
        "kpi": kpi,
        "trends": trends,
        "period": period_str,
        "dimension": dimension
    })


@router.get("/top-products", response_model=ResponseModel)
def get_top_products(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    metric: str = Query("payment_amount", description="排名指标"),
    limit: int = Query(10, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取TOP商品列表"""
    
    if dimension == "monthly":
        Model = MonthlyData
        date_col = 'month'
        visitors_col = 'visitors'
    elif dimension == "daily":
        Model = DailyData
        date_col = 'date'
        visitors_col = 'ipv'
    else:
        Model = WeeklyData
        date_col = 'week_start'
        visitors_col = 'ipv'
    
    if not period:
        latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
        period = getattr(latest, date_col) if latest else None
    
    if not period:
        return ResponseModel(data={"products": []})
    
    metric_map = {
        'payment_amount': func.sum(Model.payment_amount),
        'net_sales': func.sum(Model.payment_amount) - func.sum(Model.refund_amount),
        'visitors': func.sum(getattr(Model, visitors_col)),
        'conversion': func.avg(Model.payment_conversion),
        'roi': func.avg(Model.ad_roi),
        'refund_rate': func.sum(Model.refund_amount) / func.nullif(func.sum(Model.payment_amount), 0),
    }
    
    metric_func = metric_map.get(metric, metric_map['payment_amount'])
    
    products_query = db.query(
        Model.product_id,
        Model.product_name,
        metric_func.label('metric_value')
    ).filter(
        getattr(Model, date_col) == period
    ).group_by(
        Model.product_id,
        Model.product_name
    ).order_by(desc('metric_value')).limit(limit).all()
    
    products = []
    for i, p in enumerate(products_query, 1):
        products.append({
            "rank": i,
            "product_id": p.product_id,
            "product_name": p.product_name,
            "metric": metric,
            "value": round(float(p.metric_value or 0), 2)
        })
    
    return ResponseModel(data={
        "products": products,
        "period": str(period),
        "metric": metric
    })
