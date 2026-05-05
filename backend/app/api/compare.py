from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.models import DailyData, WeeklyData, MonthlyData, Product

router = APIRouter(prefix="/compare", tags=["周期对比"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


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
