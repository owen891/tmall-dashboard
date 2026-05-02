from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from app.core.database import get_db
from app.core.utils import get_data_model, get_latest_period, safe_float, calculate_change
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/profit", tags=["利润分析"])


def calculate_profit_metrics(payment: float, refund: float, ad_spend: float,
                             cost: float = 0, commission: float = 0,
                             freight: float = 0) -> dict:
    """计算利润指标"""
    gross_profit = payment - refund - cost
    net_profit = gross_profit - ad_spend - commission - freight

    gross_margin = (gross_profit / payment * 100) if payment > 0 else 0
    net_margin = (net_profit / payment * 100) if payment > 0 else 0
    roi = (net_profit / ad_spend * 100) if ad_spend > 0 else 0

    return {
        "gross_profit": round(gross_profit, 2),
        "net_profit": round(net_profit, 2),
        "gross_margin": round(gross_margin, 2),
        "net_margin": round(net_margin, 2),
        "roi": round(roi, 2),
        "total_cost": round(cost, 2),
        "total_ad_spend": round(ad_spend, 2),
        "total_commission": round(commission, 2),
        "total_freight": round(freight, 2)
    }


@router.get("/summary", response_model=ResponseModel)
def get_profit_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    cost_rate: float = Query(0.5, description="成本系数(默认50%)"),
    commission_rate: float = Query(0.06, description="佣金系数(默认6%)"),
    freight_rate: float = Query(0.02, description="运费系数(默认2%)"),
    db: Session = Depends(get_db)
):
    """获取利润汇总"""
    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"summary": {}, "trends": []})

    data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == period).first()

    payment = safe_float(data.payment) if data else 0
    refund = safe_float(data.refund) if data else 0
    ad_spend = safe_float(data.ad_spend) if data else 0

    cost = payment * cost_rate
    commission = payment * commission_rate
    freight = payment * freight_rate

    metrics = calculate_profit_metrics(payment, refund, ad_spend, cost, commission, freight)

    return ResponseModel(data={
        "period": str(period),
        "dimension": dimension,
        "payment": round(payment, 2),
        "metrics": metrics,
        "rates": {
            "cost_rate": cost_rate,
            "commission_rate": commission_rate,
            "freight_rate": freight_rate
        }
    })


@router.get("/products", response_model=ResponseModel)
def get_product_profits(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    tier: Optional[str] = Query(None, description="分层筛选"),
    sort_by: str = Query("net_profit", description="排序字段"),
    order: str = Query("desc", description="排序方向"),
    limit: int = Query(50, description="返回数量"),
    cost_rate: float = Query(0.5, description="成本系数"),
    db: Session = Depends(get_db)
):
    """获取商品利润排行"""
    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"products": []})

    query = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == period)

    if tier:
        query = query.join(Product, Model.product_id == Product.product_id).filter(
            Product.tier == tier
        )

    query = query.group_by(Model.product_id)

    if order == "desc":
        query = query.order_by(desc(f"payment"))
    else:
        query = query.order_by(func.sum(Model.payment_amount))

    results = query.limit(limit).all()

    products = []
    for r in results:
        payment = safe_float(r.payment)
        refund = safe_float(r.refund)
        ad_spend = safe_float(r.ad_spend)
        cost = payment * cost_rate
        commission = payment * 0.06
        freight = payment * 0.02

        metrics = calculate_profit_metrics(payment, refund, ad_spend, cost, commission, freight)

        product = db.query(Product).filter(Product.product_id == r.product_id).first()
        if product:
            products.append({
                "product_id": r.product_id,
                "title": product.title,
                "tier": product.tier,
                "payment": round(payment, 2),
                "metrics": metrics
            })

    products.sort(key=lambda x: x['metrics'].get(sort_by, 0), reverse=(order == "desc"))

    return ResponseModel(data={
        "period": str(period),
        "dimension": dimension,
        "products": products
    })


@router.get("/trends", response_model=ResponseModel)
def get_profit_trends(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    periods: int = Query(12, description="周期数量"),
    cost_rate: float = Query(0.5, description="成本系数"),
    db: Session = Depends(get_db)
):
    """获取利润趋势"""
    from app.core.utils import get_prev_period

    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"trends": []})

    trends = []
    current = str(period)

    for _ in range(periods):
        data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ).filter(getattr(Model, date_col) == current).first()

        if data:
            payment = safe_float(data.payment)
            refund = safe_float(data.refund)
            ad_spend = safe_float(data.ad_spend)
            cost = payment * cost_rate
            commission = payment * 0.06
            freight = payment * 0.02

            metrics = calculate_profit_metrics(payment, refund, ad_spend, cost, commission, freight)

            trends.append({
                "period": current,
                "payment": round(payment, 2),
                "metrics": metrics
            })

        current = get_prev_period(current, dimension)

    trends.reverse()

    return ResponseModel(data={
        "trends": trends,
        "dimension": dimension,
        "cost_rate": cost_rate
    })


@router.get("/by-tier", response_model=ResponseModel)
def get_profit_by_tier(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    cost_rate: float = Query(0.5, description="成本系数"),
    db: Session = Depends(get_db)
):
    """按分层获取利润分布"""
    Model, date_col, visitors_col = get_data_model(dimension)

    if not period:
        period = get_latest_period(Model, date_col, db)

    if not period:
        return ResponseModel(data={"tiers": []})

    tiers = db.query(
        Product.tier,
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).join(Model, Product.product_id == Model.product_id).filter(
        getattr(Model, date_col) == period
    ).group_by(Product.tier).all()

    result = []
    for t in tiers:
        payment = safe_float(t.payment)
        refund = safe_float(t.refund)
        ad_spend = safe_float(t.ad_spend)
        cost = payment * cost_rate
        commission = payment * 0.06
        freight = payment * 0.02

        metrics = calculate_profit_metrics(payment, refund, ad_spend, cost, commission, freight)

        result.append({
            "tier": t.tier or "未分类",
            "payment": round(payment, 2),
            "metrics": metrics
        })

    return ResponseModel(data={
        "period": str(period),
        "dimension": dimension,
        "tiers": result
    })
