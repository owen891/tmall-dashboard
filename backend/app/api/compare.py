from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.utils import get_latest_period, get_prev_period, safe_float
from app.schemas.common import ResponseModel
from app.models import DailyData, WeeklyData, MonthlyData, Product

router = APIRouter(prefix="/compare", tags=["周期对比"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def _get_model(dimension):
    if dimension == "monthly":
        return MonthlyData, 'month', 'visitors'
    elif dimension == "daily":
        return DailyData, 'date', 'ipv'
    return WeeklyData, 'week_start', 'ipv'


def _calc_change_pct(current, previous):
    if not previous or previous == 0:
        return 0 if current == 0 else None
    pct = round((current - previous) / previous * 100, 1)
    return pct


def _get_change_status(pct):
    if pct is None:
        return 'stable'
    if pct > 5:
        return 'up'
    elif pct < -5:
        return 'down'
    return 'stable'


@router.get("/summary", response_model=ResponseModel)
def get_compare_summary(
    dimension: str = Query("monthly", description="时间维度"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = _get_model(dimension)

    current_period = get_latest_period(Model, date_col, db)
    if not current_period:
        return ResponseModel(data={
            'current_period': None,
            'previous_period': None,
            'comparison': {}
        })

    previous_period = get_prev_period(current_period, dimension)

    def query_kpi(period):
        row = db.query(
            func.sum(Model.payment_amount).label('gmv'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
            func.avg(Model.ad_roi).label('roi'),
        ).filter(getattr(Model, date_col) == period).first()
        return row

    kpi_cur = query_kpi(current_period)
    kpi_prev = query_kpi(previous_period)

    cur_payment = safe_float(getattr(kpi_cur, 'gmv', 0)) if kpi_cur else 0
    cur_visitors = safe_float(getattr(kpi_cur, 'visitors', 0)) if kpi_cur else 0
    cur_refund = safe_float(getattr(kpi_cur, 'refund', 0)) if kpi_cur else 0
    cur_conversion = safe_float(getattr(kpi_cur, 'conversion', 0)) if kpi_cur else 0
    cur_ad_spend = safe_float(getattr(kpi_cur, 'ad_spend', 0)) if kpi_cur else 0

    prev_payment = safe_float(getattr(kpi_prev, 'gmv', 0)) if kpi_prev else 0
    prev_visitors = safe_float(getattr(kpi_prev, 'visitors', 0)) if kpi_prev else 0
    prev_refund = safe_float(getattr(kpi_prev, 'refund', 0)) if kpi_prev else 0
    prev_conversion = safe_float(getattr(kpi_prev, 'conversion', 0)) if kpi_prev else 0
    prev_ad_spend = safe_float(getattr(kpi_prev, 'ad_spend', 0)) if kpi_prev else 0

    def make_comparison(cur_val, prev_val):
        pct = _calc_change_pct(cur_val, prev_val)
        return {
            'change_percent': pct if pct is not None else 0,
            'status': _get_change_status(pct)
        }

    comparison = {
        'payment': make_comparison(cur_payment, prev_payment),
        'visitors': make_comparison(cur_visitors, prev_visitors),
        'refund': make_comparison(cur_refund, prev_refund),
        'conversion': make_comparison(cur_conversion, prev_conversion),
        'ad_spend': make_comparison(cur_ad_spend, prev_ad_spend),
    }

    return ResponseModel(data={
        'current_period': {
            'period': current_period,
            'payment': cur_payment,
            'visitors': cur_visitors,
            'refund': cur_refund,
            'conversion': cur_conversion,
            'ad_spend': cur_ad_spend,
        },
        'previous_period': {
            'period': previous_period,
            'payment': prev_payment,
            'visitors': prev_visitors,
            'refund': prev_refund,
            'conversion': prev_conversion,
            'ad_spend': prev_ad_spend,
        },
        'comparison': comparison,
    })


@router.get("/products", response_model=ResponseModel)
def get_compare_products(
    dimension: str = Query("monthly", description="时间维度"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = _get_model(dimension)

    current_period = get_latest_period(Model, date_col, db)
    if not current_period:
        return ResponseModel(data={'products': []})

    previous_period = get_prev_period(current_period, dimension)

    def query_products(period):
        rows = db.query(
            Model.product_id,
            Product.title,
            Product.tier,
            func.sum(Model.payment_amount).label('total_payment'),
        ).join(Product, Model.product_id == Product.product_id).filter(
            getattr(Model, date_col) == period,
        ).group_by(Model.product_id, Product.title, Product.tier).order_by(
            desc(func.sum(Model.payment_amount))
        ).all()
        return rows

    products_cur = query_products(current_period)
    products_prev = query_products(previous_period)

    cur_map = {p.product_id: p for p in products_cur}
    prev_map = {p.product_id: p for p in products_prev}

    all_ids = set(cur_map.keys()) | set(prev_map.keys())
    products = []

    for pid in all_ids:
        cur = cur_map.get(pid)
        prev = prev_map.get(pid)

        cur_val = safe_float(cur.total_payment) if cur else 0
        prev_val = safe_float(prev.total_payment) if prev else 0

        pct = _calc_change_pct(cur_val, prev_val)

        products.append({
            'product_id': pid,
            'title': (cur.title if cur else (prev.title if prev else '')),
            'tier': (cur.tier if cur else (prev.tier if prev else '')),
            'current_value': cur_val,
            'previous_value': prev_val,
            'comparison': {
                'change_percent': pct if pct is not None else 0,
                'status': _get_change_status(pct),
            }
        })

    products.sort(key=lambda x: abs(x['comparison']['change_percent']), reverse=True)

    return ResponseModel(data={
        'products': products[:limit],
        'current_period': current_period,
        'previous_period': previous_period,
    })


@router.get("/trends", response_model=ResponseModel)
def get_compare_trends(
    dimension: str = Query("monthly", description="时间维度"),
    periods: int = Query(12, description="历史周期数"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = _get_model(dimension)

    latest_periods = db.query(getattr(Model, date_col)).distinct().order_by(
        desc(getattr(Model, date_col))
    ).limit(periods).all()

    trends = []

    for period_row in reversed(latest_periods):
        period = period_row[0]
        period_str = period.isoformat() if hasattr(period, 'isoformat') else str(period)

        prev_period = get_prev_period(period_str, dimension)

        cur_row = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
        ).filter(getattr(Model, date_col) == period).first()

        prev_row = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
        ).filter(getattr(Model, date_col) == prev_period).first()

        trends.append({
            'period': period_str,
            'current': {
                'payment': safe_float(cur_row.payment) if cur_row else 0,
                'visitors': safe_float(cur_row.visitors) if cur_row else 0,
            },
            'previous': {
                'payment': safe_float(prev_row.payment) if prev_row else 0,
                'visitors': safe_float(prev_row.visitors) if prev_row else 0,
            }
        })

    return ResponseModel(data={
        'trends': trends,
        'dimension': dimension,
    })


@router.get("", response_model=ResponseModel)
def compare_periods(
    dim: str = Query("weekly", description="时间维度"),
    period_a: str = Query(..., description="周期A"),
    period_b: str = Query(..., description="周期B"),
    db: Session = Depends(get_db)
):
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData

    def query_kpi(period):
        row = db.query(
            func.sum(Model.payment_amount).label('gmv'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(Model.payment_amount - Model.refund_amount).label('net_sales'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
            func.avg(Model.ad_roi).label('roi'),
        ).filter(getattr(Model, date_col) == period).first()
        return row

    kpi_a = query_kpi(period_a)
    kpi_b = query_kpi(period_b)

    kpi_compare = {}
    if kpi_a and kpi_b:
        metrics = ['gmv', 'net_sales', 'visitors', 'ad_spend', 'conversion', 'roi']
        for key in metrics:
            va = getattr(kpi_a, key, 0) or 0
            vb = getattr(kpi_b, key, 0) or 0
            change = round((vb - va) / va * 100, 1) if va > 0 else None
            kpi_compare[key] = {
                'period_a': float(va),
                'period_b': float(vb),
                'change_pct': change,
            }

        ra = getattr(kpi_a, 'refund', 0) or 0
        rb = getattr(kpi_b, 'refund', 0) or 0
        gmv_a = getattr(kpi_a, 'gmv', 0) or 0
        gmv_b = getattr(kpi_b, 'gmv', 0) or 0
        refund_rate_a = ra / gmv_a if gmv_a > 0 else 0
        refund_rate_b = rb / gmv_b if gmv_b > 0 else 0
        kpi_compare['refund_rate'] = {
            'period_a': refund_rate_a,
            'period_b': refund_rate_b,
            'change_pct': round((refund_rate_b - refund_rate_a) * 100, 1),
        }

    def query_products(period):
        rows = db.query(
            Model.product_id,
            Product.title,
            Product.style,
            Model.payment_amount,
            Model.ad_spend,
        ).join(Product, Model.product_id == Product.product_id).filter(
            getattr(Model, date_col) == period,
            Product.status == 'active'
        ).order_by(desc(Model.payment_amount)).all()
        return rows

    products_a = query_products(period_a)
    products_b = query_products(period_b)

    rank_a = {p.product_id: i + 1 for i, p in enumerate(products_a) if p.payment_amount and p.payment_amount > 0}
    rank_b = {p.product_id: i + 1 for i, p in enumerate(products_b) if p.payment_amount and p.payment_amount > 0}
    amount_a = {p.product_id: p.payment_amount or 0 for p in products_a}
    amount_b = {p.product_id: p.payment_amount or 0 for p in products_b}
    title_map = {p.product_id: p.title for p in products_a}
    style_map = {p.product_id: p.style for p in products_a}
    for p in products_b:
        if p.product_id not in title_map:
            title_map[p.product_id] = p.title
            style_map[p.product_id] = p.style

    product_changes = []
    all_ids = set(rank_a.keys()) | set(rank_b.keys())

    for pid in all_ids:
        r_a = rank_a.get(pid)
        r_b = rank_b.get(pid)

        if r_a and r_b:
            diff = r_a - r_b
            status = 'up' if diff > 0 else ('down' if diff < 0 else 'flat')
            product_changes.append({
                'product_id': pid,
                'title': title_map.get(pid, ''),
                'style': style_map.get(pid, ''),
                'rank_a': r_a,
                'rank_b': r_b,
                'rank_diff': diff,
                'amount_a': float(amount_a.get(pid, 0) or 0),
                'amount_b': float(amount_b.get(pid, 0) or 0),
                'status': status,
            })
        elif r_a and not r_b:
            product_changes.append({
                'product_id': pid,
                'title': title_map.get(pid, ''),
                'style': style_map.get(pid, ''),
                'rank_a': r_a,
                'rank_b': None,
                'rank_diff': None,
                'amount_a': float(amount_a.get(pid, 0) or 0),
                'amount_b': 0,
                'status': 'exit',
            })
        else:
            product_changes.append({
                'product_id': pid,
                'title': title_map.get(pid, ''),
                'style': style_map.get(pid, ''),
                'rank_a': None,
                'rank_b': r_b,
                'rank_diff': None,
                'amount_a': 0,
                'amount_b': float(amount_b.get(pid, 0) or 0),
                'status': 'new',
            })

    product_changes.sort(key=lambda x: x.get('rank_diff') or 0, reverse=True)

    return ResponseModel(data={
        'period_a': period_a,
        'period_b': period_b,
        'dimension': dim,
        'kpi_compare': kpi_compare,
        'product_changes': product_changes[:50],
    })
