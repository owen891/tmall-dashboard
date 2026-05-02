from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from app.core.database import get_db
from app.core.utils import get_data_model, get_latest_period, safe_float, calculate_change
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/compare", tags=["数据对比"])


def get_same_period_last_year(period: str, dimension: str) -> str:
    """获取去年同周期"""
    from datetime import datetime

    try:
        if dimension == 'monthly':
            y, m = str(period).split('-')
            return f"{int(y) - 1}-{m}"
        elif dimension == 'weekly':
            y, mm, dd = str(period).split('-')
            return f"{int(y) - 1}-{mm}-{dd}"
        else:
            dt = datetime.strptime(str(period), '%Y-%m-%d')
            prev_year = dt.replace(year=dt.year - 1)
            return prev_year.strftime('%Y-%m-%d')
    except (ValueError, IndexError, AttributeError):
        return period


def calculate_comparison(current: float, previous: float) -> dict:
    """计算对比结果"""
    change = current - previous
    percent = ((current - previous) / previous * 100) if previous != 0 else 0

    if abs(percent) > 5:
        status = "up" if percent > 0 else "down"
    else:
        status = "stable"

    return {
        "current": round(current, 2),
        "previous": round(previous, 2),
        "change": round(change, 2),
        "change_percent": round(percent, 1),
        "status": status
    }


@router.get("/summary", response_model=ResponseModel)
def get_compare_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取同比汇总对比"""
    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"current": {}, "yoy": {}})

    current_period = str(period)
    previous_period = get_same_period_last_year(current_period, dimension)

    current_data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == current_period).first()

    previous_data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == previous_period).first()

    current_payment = safe_float(current_data.payment) if current_data else 0
    previous_payment = safe_float(previous_data.payment) if previous_data else 0

    current_refund = safe_float(current_data.refund) if current_data else 0
    previous_refund = safe_float(previous_data.refund) if previous_data else 0

    current_visitors = int(safe_float(current_data.visitors)) if current_data else 0
    previous_visitors = int(safe_float(previous_data.visitors)) if previous_data else 0

    current_conversion = safe_float(current_data.conversion) if current_data else 0
    previous_conversion = safe_float(previous_data.conversion) if previous_data else 0

    current_ad_spend = safe_float(current_data.ad_spend) if current_data else 0
    previous_ad_spend = safe_float(previous_data.ad_spend) if previous_data else 0

    return ResponseModel(data={
        "dimension": dimension,
        "current_period": {
            "period": current_period,
            "payment": round(current_payment, 2),
            "refund": round(current_refund, 2),
            "visitors": current_visitors,
            "conversion": round(current_conversion * 100, 2),
            "ad_spend": round(current_ad_spend, 2)
        },
        "previous_period": {
            "period": previous_period,
            "payment": round(previous_payment, 2),
            "refund": round(previous_refund, 2),
            "visitors": previous_visitors,
            "conversion": round(previous_conversion * 100, 2),
            "ad_spend": round(previous_ad_spend, 2)
        },
        "comparison": {
            "payment": calculate_comparison(current_payment, previous_payment),
            "refund": calculate_comparison(current_refund, previous_refund),
            "visitors": calculate_comparison(current_visitors, previous_visitors),
            "conversion": calculate_comparison(current_conversion * 100, previous_conversion * 100),
            "ad_spend": calculate_comparison(current_ad_spend, previous_ad_spend)
        }
    })


@router.get("/products", response_model=ResponseModel)
def get_compare_products(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    metric: str = Query("payment", description="对比指标"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取商品同比对比"""
    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"products": []})

    current_period = str(period)
    previous_period = get_same_period_last_year(current_period, dimension)

    current_data = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
    ).filter(getattr(Model, date_col) == current_period).group_by(Model.product_id).all()

    previous_data_map = {}
    previous_data = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
    ).filter(getattr(Model, date_col) == previous_period).group_by(Model.product_id).all()

    for p in previous_data:
        previous_data_map[p.product_id] = p

    products = []
    for c in current_data:
        p = previous_data_map.get(c.product_id)
        if not p:
            continue

        product = db.query(Product).filter(Product.product_id == c.product_id).first()

        current_value = safe_float(getattr(c, metric)) if metric != 'conversion' else safe_float(c.conversion)
        previous_value = safe_float(getattr(p, metric)) if metric != 'conversion' else safe_float(p.conversion)

        if metric == 'conversion':
            current_value *= 100
            previous_value *= 100

        comparison = calculate_comparison(current_value, previous_value)

        products.append({
            "product_id": c.product_id,
            "title": product.title if product else "",
            "tier": product.tier if product else "",
            "current_value": round(current_value, 2),
            "previous_value": round(previous_value, 2),
            "comparison": comparison
        })

    products.sort(key=lambda x: x['comparison']['change_percent'], reverse=True)

    return ResponseModel(data={
        "dimension": dimension,
        "current_period": current_period,
        "previous_period": previous_period,
        "metric": metric,
        "products": products[:limit]
    })


@router.get("/trends", response_model=ResponseModel)
def get_compare_trends(
    dimension: str = Query("monthly", description="时间维度(建议用monthly)"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    db: Session = Depends(get_db)
):
    """获取同比趋势对比"""
    from app.core.utils import get_prev_period

    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"trends": []})

    trends = []
    current = str(period)

    for _ in range(periods):
        previous = get_same_period_last_year(current, dimension)

        current_data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
        ).filter(getattr(Model, date_col) == current).first()

        previous_data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
        ).filter(getattr(Model, date_col) == previous).first()

        current_payment = safe_float(current_data.payment) if current_data else 0
        previous_payment = safe_float(previous_data.payment) if previous_data else 0

        current_visitors = int(safe_float(current_data.visitors)) if current_data else 0
        previous_visitors = int(safe_float(previous_data.visitors)) if previous_data else 0

        trends.append({
            "period": current,
            "current": {
                "payment": round(current_payment, 2),
                "visitors": current_visitors
            },
            "previous": {
                "period": previous,
                "payment": round(previous_payment, 2),
                "visitors": previous_visitors
            },
            "payment_comparison": calculate_comparison(current_payment, previous_payment),
            "visitors_comparison": calculate_comparison(current_visitors, previous_visitors)
        })

        if dimension == 'monthly':
            y, m = current.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            current = f"{y}-{m:02d}"
        else:
            current = get_prev_period(current, dimension)

    trends.reverse()

    return ResponseModel(data={
        "dimension": dimension,
        "trends": trends
    })
