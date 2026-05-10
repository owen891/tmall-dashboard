from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.review import Refund
from app.models import Product

router = APIRouter(prefix="/refunds", tags=["退款分析"])


class RefundRateTrend(BaseModel):
    date: str
    refund_rate: float
    refund_amount: float
    refund_count: int


class RefundReasonStat(BaseModel):
    reason: str
    count: int
    percentage: float
    avg_amount: float


class ProductRefundStat(BaseModel):
    product_id: int
    product_name: str
    refund_rate: float
    refund_count: int
    refund_amount: float
    avg_refund_days: float
    risk_level: str


class RefundSummary(BaseModel):
    total_refund_count: int
    total_refund_amount: float
    avg_refund_rate: float
    avg_refund_days: float
    top_risk_products: List[ProductRefundStat]


class RefundTrendResponse(BaseModel):
    dimension: str
    trends: List[RefundRateTrend]
    summary: RefundSummary


class RefundAlert(BaseModel):
    product_id: int
    product_name: str
    refund_rate: float
    threshold: float
    severity: str
    message: str


@router.get("/summary", response_model=dict)
def get_refund_summary(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        func.count(Refund.id).label("total_refund_count"),
        func.coalesce(func.sum(Refund.refund_amount), 0).label("total_refund_amount"),
        func.avg(Refund.refund_rate).label("avg_refund_rate"),
        func.avg(Refund.refund_days).label("avg_refund_days")
    )

    if start_date:
        query = query.filter(Refund.refund_date >= start_date)
    if end_date:
        query = query.filter(Refund.refund_date <= end_date)

    result = query.first()
    total_count = result.total_refund_count or 0
    total_amount = float(result.total_refund_amount or 0)
    avg_rate = float(result.avg_refund_rate or 0)
    avg_days = float(result.avg_refund_days or 0)

    high_risk_query = db.query(
        Refund.product_id,
        Refund.product_name,
        func.avg(Refund.refund_rate).label("refund_rate"),
        func.count(Refund.id).label("refund_count"),
        func.sum(Refund.refund_amount).label("refund_amount"),
        func.avg(Refund.refund_days).label("avg_refund_days")
    ).group_by(Refund.product_id, Refund.product_name)

    if start_date:
        high_risk_query = high_risk_query.filter(Refund.refund_date >= start_date)
    if end_date:
        high_risk_query = high_risk_query.filter(Refund.refund_date <= end_date)

    high_risk_products = high_risk_query.order_by(func.avg(Refund.refund_rate).desc()).limit(10).all()

    risk_products = []
    for p in high_risk_products:
        risk_level = "high" if p.refund_rate > 5 else ("medium" if p.refund_rate > 3 else "low")
        risk_products.append(ProductRefundStat(
            product_id=p.product_id,
            product_name=p.product_name,
            refund_rate=float(p.refund_rate or 0),
            refund_count=p.refund_count,
            refund_amount=float(p.refund_amount or 0),
            avg_refund_days=float(p.avg_refund_days or 0),
            risk_level=risk_level
        ))

    summary = RefundSummary(
        total_refund_count=total_count,
        total_refund_amount=total_amount,
        avg_refund_rate=avg_rate,
        avg_refund_days=avg_days,
        top_risk_products=risk_products
    )

    return {"code": 200, "data": summary.model_dump()}


@router.get("/trends", response_model=dict)
def get_refund_trends(
    dimension: str = Query("weekly", description="时间维度"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if dimension == "daily":
        date_trunc = func.date(Refund.refund_date)
    elif dimension == "monthly":
        date_trunc = func.strftime("%Y-%m", Refund.refund_date)
    else:
        year = func.strftime("%Y", Refund.refund_date)
        week = func.strftime("%W", Refund.refund_date)
        date_trunc = func.concat(year, "-W", week)

    query = db.query(
        date_trunc.label("date"),
        func.avg(Refund.refund_rate).label("refund_rate"),
        func.sum(Refund.refund_amount).label("refund_amount"),
        func.count(Refund.id).label("refund_count")
    )

    if start_date:
        query = query.filter(Refund.refund_date >= start_date)
    if end_date:
        query = query.filter(Refund.refund_date <= end_date)

    results = query.group_by(date_trunc).order_by(date_trunc).all()

    trends = [RefundRateTrend(
        date=str(r.date or ""),
        refund_rate=float(r.refund_rate or 0),
        refund_amount=float(r.refund_amount or 0),
        refund_count=r.refund_count or 0
    ) for r in results]

    summary_query = db.query(
        func.count(Refund.id).label("total_refund_count"),
        func.coalesce(func.sum(Refund.refund_amount), 0).label("total_refund_amount"),
        func.avg(Refund.refund_rate).label("avg_refund_rate"),
        func.avg(Refund.refund_days).label("avg_refund_days")
    )

    if start_date:
        summary_query = summary_query.filter(Refund.refund_date >= start_date)
    if end_date:
        summary_query = summary_query.filter(Refund.refund_date <= end_date)

    summary_result = summary_query.first()

    high_risk_products_query = db.query(
        Refund.product_id,
        Refund.product_name,
        func.avg(Refund.refund_rate).label("refund_rate"),
        func.count(Refund.id).label("refund_count"),
        func.sum(Refund.refund_amount).label("refund_amount"),
        func.avg(Refund.refund_days).label("avg_refund_days")
    ).group_by(Refund.product_id, Refund.product_name)

    if start_date:
        high_risk_products_query = high_risk_products_query.filter(Refund.refund_date >= start_date)
    if end_date:
        high_risk_products_query = high_risk_products_query.filter(Refund.refund_date <= end_date)

    high_risk_products = high_risk_products_query.order_by(func.avg(Refund.refund_rate).desc()).limit(10).all()

    risk_products = []
    for p in high_risk_products:
        risk_level = "high" if p.refund_rate > 5 else ("medium" if p.refund_rate > 3 else "low")
        risk_products.append(ProductRefundStat(
            product_id=p.product_id,
            product_name=p.product_name,
            refund_rate=float(p.refund_rate or 0),
            refund_count=p.refund_count,
            refund_amount=float(p.refund_amount or 0),
            avg_refund_days=float(p.avg_refund_days or 0),
            risk_level=risk_level
        ))

    summary = RefundSummary(
        total_refund_count=summary_result.total_refund_count or 0,
        total_refund_amount=float(summary_result.total_refund_amount or 0),
        avg_refund_rate=float(summary_result.avg_refund_rate or 0),
        avg_refund_days=float(summary_result.avg_refund_days or 0),
        top_risk_products=risk_products
    )

    return {"code": 200, "data": RefundTrendResponse(
        dimension=dimension,
        trends=trends,
        summary=summary
    ).model_dump()}


@router.get("/reasons", response_model=dict)
def get_refund_reasons(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        Refund.refund_reason,
        func.count(Refund.id).label("count"),
        func.sum(Refund.refund_amount).label("total_amount"),
        func.avg(Refund.refund_amount).label("avg_amount")
    )

    if start_date:
        query = query.filter(Refund.refund_date >= start_date)
    if end_date:
        query = query.filter(Refund.refund_date <= end_date)
    if product_id:
        query = query.filter(Refund.product_id == product_id)

    results = query.group_by(Refund.refund_reason).order_by(func.count(Refund.id).desc()).all()

    total_count = sum(r.count for r in results)

    reasons = []
    for r in results:
        percentage = (r.count / total_count * 100) if total_count > 0 else 0
        reasons.append(RefundReasonStat(
            reason=r.refund_reason or "未知",
            count=r.count,
            percentage=round(percentage, 2),
            avg_amount=float(r.avg_amount or 0)
        ))

    return {"code": 200, "data": [r.model_dump() for r in reasons]}


@router.get("/alerts", response_model=dict)
def get_refund_alerts(
    threshold: float = Query(5.0, description="退款率预警阈值(%)"),
    db: Session = Depends(get_db)
):
    latest_refunds = db.query(
        Refund.product_id,
        Refund.product_name,
        Refund.refund_date,
        Refund.refund_rate
    ).order_by(Refund.product_id, Refund.refund_date.desc()).all()

    product_latest = {}
    for r in latest_refunds:
        if r.product_id not in product_latest:
            product_latest[r.product_id] = r

    alerts = []
    for product_id, refund_info in product_latest.items():
        if refund_info.refund_rate > threshold:
            severity = "critical" if refund_info.refund_rate > threshold * 2 else "warning"
            alerts.append(RefundAlert(
                product_id=product_id,
                product_name=refund_info.product_name,
                refund_rate=float(refund_info.refund_rate),
                threshold=threshold,
                severity=severity,
                message=f"商品{refund_info.product_name}退款率({refund_info.refund_rate}%)超过阈值({threshold}%)"
            ))

    alerts.sort(key=lambda x: x.refund_rate, reverse=True)

    return {"code": 200, "data": [a.model_dump() for a in alerts]}


@router.get("/product/{product_id}", response_model=dict)
def get_product_refunds(
    product_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Refund).filter(Refund.product_id == product_id)

    if start_date:
        query = query.filter(Refund.refund_date >= start_date)
    if end_date:
        query = query.filter(Refund.refund_date <= end_date)

    refunds = query.order_by(Refund.refund_date.desc()).all()

    refund_list = []
    for r in refunds:
        refund_list.append({
            "id": r.id,
            "refund_date": str(r.refund_date) if r.refund_date else None,
            "refund_rate": float(r.refund_rate) if r.refund_rate else 0,
            "refund_count": r.refund_count or 0,
            "refund_amount": float(r.refund_amount) if r.refund_amount else 0,
            "refund_reason": r.refund_reason,
            "refund_days": float(r.refund_days) if r.refund_days else 0
        })

    stats_query = db.query(
        func.count(Refund.id).label("total_count"),
        func.avg(Refund.refund_rate).label("avg_rate"),
        func.sum(Refund.refund_amount).label("total_amount"),
        func.avg(Refund.refund_days).label("avg_days")
    ).filter(Refund.product_id == product_id)

    if start_date:
        stats_query = stats_query.filter(Refund.refund_date >= start_date)
    if end_date:
        stats_query = stats_query.filter(Refund.refund_date <= end_date)

    stats = stats_query.first()

    return {
        "code": 200,
        "data": {
            "refunds": refund_list,
            "summary": {
                "total_count": stats.total_count or 0,
                "avg_rate": float(stats.avg_rate or 0),
                "total_amount": float(stats.total_amount or 0),
                "avg_days": float(stats.avg_days or 0)
            }
        }
    }
