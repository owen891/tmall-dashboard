from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, case, text
from typing import Optional, List, Dict, Any
from app.core.database import get_db
from app.core.cache import cached
from app.models import DailyData, WeeklyData, MonthlyData, Product, ProductTag, ProductNote, OperationAction
from app.schemas.common import ResponseModel
import io
import csv
from datetime import datetime

router = APIRouter(prefix="/products", tags=["商品运营"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}

SORT_WHITELIST = [
    'payment_amount', 'net_sales', 'refund_rate', 'refund_amount',
    'visitors', 'conversion', 'aov', 'ad_spend', 'roi', 'ad_ratio',
    'payment_count', 'order_count', 'page_views', 'uv_value',
    'search_visitors', 'search_ratio', 'cart_rate', 'fav_rate',
    'bounce_rate', 'avg_stay_duration', 'score',
    'category', 'tier', 'style', 'scene', 'title',
    'keyword_spend', 'keyword_roi', 'keyword_visitors', 'keyword_ppc',
    'crowd_spend', 'crowd_roi', 'crowd_visitors', 'crowd_ppc',
    'site_spend', 'site_roi', 'site_visitors', 'site_ppc',
    'overall_roi', 'paid_ratio', 'refund_paid_ratio',
    'repurchase_rate', 'cross_sell_rate', 'buyers', 'avg_order_value',
    'cart_qty', 'fav_users', 'click_rate', 'net_sales',
    'paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv',
    'cart_users', 'industry_ctr', 'cross_sell_qty', 'cross_sell_categories',
    'new_buyers', 'new_buyer_ratio',
    'impressions', 'clicks', 'cost', 'ctr', 'cpc', 'cpm',
    'direct_gmv', 'indirect_gmv', 'total_gmv', 'total_orders',
    'direct_orders', 'indirect_orders', 'click_conversion', 'presale_roi',
    'total_cost', 'cart_adds', 'direct_cart_adds', 'indirect_cart_adds',
    'favs', 'store_favs', 'store_fav_cost', 'total_fav_cart', 'total_fav_cart_cost',
    'item_fav_cart', 'item_fav_cart_cost', 'total_favs', 'item_fav_cost',
    'item_fav_rate', 'cart_cost',
    'manager', 'product_id', 'list_date',
]

WEEKLY_ONLY_COLS = [
    'presale_amount', 'presale_qty', 'ipv', 'pv',
    'search_ipv', 'recommend_ipv', 'paid_ipv', 'organic_ipv',
    'search_click_rate',
    'repurchase_users', 'cross_sell_qty', 
    'category_width', 'industry_ctr',
    'buyers', 'cart_users', 'cart_qty', 'fav_users',
    'uv_value', 'search_conversion', 'search_visitors', 'click_rate',
]

MONTHLY_ONLY_COLS = [
    'overall_roi', 'paid_ratio', 'refund_paid_ratio',
    'keyword_spend', 'keyword_sales', 'keyword_roi', 'keyword_visitors', 'keyword_ppc',
    'crowd_spend', 'crowd_sales', 'crowd_roi', 'crowd_visitors', 'crowd_ppc',
    'site_spend', 'site_sales', 'site_roi', 'site_visitors', 'site_ppc',
    'paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv',
    'cross_sell_qty', 'cross_sell_categories',
    'uv_value', 'search_visitors', 'search_ratio', 'search_conversion',
    'cart_qty', 'click_rate', 
    'cart_users', 'new_buyers', 'new_buyer_ratio',
    'visitors', 'page_views', 'buyers', 'payment_qty',
    'guide_visits', 'guide_visitors', 'guide_potential', 'guide_potential_ratio',
    'impressions', 'clicks', 'cost', 'ctr', 'cpc', 'cpm',
    'total_gmv', 'total_orders', 'direct_gmv', 'indirect_gmv',
    'direct_orders', 'indirect_orders', 'click_conversion', 'presale_roi',
    'total_cost', 'cart_adds', 'direct_cart_adds', 'indirect_cart_adds',
    'favs', 'store_favs', 'store_fav_cost', 'total_fav_cart', 'total_fav_cart_cost',
    'item_fav_cart', 'item_fav_cart_cost', 'total_favs', 'item_fav_cost',
    'item_fav_rate', 'cart_cost',
]

ALL_COMMON_COLS = []


def get_latest_period(Model, date_col, db):
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        return getattr(latest, date_col)
    return None


def calc_score(row_data: dict) -> float:
    score = 50.0
    conv = row_data.get('conversion', 0) or 0
    roi = row_data.get('overall_roi', 0) or row_data.get('roi', 0) or 0
    refund = row_data.get('refund_rate', 0) or 0
    uv = row_data.get('uv_value', 0) or 0
    search = row_data.get('search_ratio', 0) or 0
    
    score += min(conv * 5, 20)
    score += min(roi * 1.5, 15)
    score -= min(refund * 1.5, 20)
    score += min(uv * 0.5, 10)
    score += min(search * 5, 5)
    
    return round(max(0, min(100, score)), 1)


def get_prev_period(period: str, dim: str) -> str:
    try:
        if dim == 'monthly':
            y, m = str(period).split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        else:
            from datetime import datetime, timedelta
            d = datetime.strptime(str(period), '%Y-%m-%d')
            prev = d - timedelta(days=7 if dim == 'weekly' else 1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period


def build_product_query(dimension: str, period: str, db: Session):
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    base_cols = [
        Model.product_id,
        func.max(Product.title).label('title'),
        func.max(Product.image_url).label('image_url'),
        func.max(Product.category).label('category'),
        func.max(Product.tier).label('tier'),
        func.max(Product.style).label('style'),
        func.max(Product.scene).label('scene'),
        func.max(Product.manager).label('manager'),
        func.max(Product.list_date).label('list_date'),
        func.max(Product.status).label('status'),
        func.max(Product.starred).label('starred'),
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.avg(Model.ad_roi).label('roi'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ]
    
    if dimension == 'monthly':
        base_cols.append(func.sum(Model.payment_qty).label('payment_count'))
    elif dimension == 'daily':
        base_cols.append(func.sum(Model.payment_qty).label('payment_count'))
    else:
        base_cols.append(func.sum(Model.presale_qty).label('payment_count'))
    
    if hasattr(Model, 'order_count'):
        base_cols.append(func.sum(Model.order_count).label('order_count'))
    
    for col_name in ALL_COMMON_COLS:
        if hasattr(Model, col_name):
            if col_name in ['payment_conversion', 'cart_rate', 'fav_rate', 'bounce_rate', 'avg_stay_duration', 'ad_roi', 'repurchase_rate', 'cross_sell_rate']:
                base_cols.append(func.avg(getattr(Model, col_name)).label(col_name))
            else:
                base_cols.append(func.sum(getattr(Model, col_name)).label(col_name))
    
    if dimension == 'weekly':
        weekly_cols = []
        for col_name in WEEKLY_ONLY_COLS:
            if hasattr(Model, col_name):
                if col_name in ['payment_conversion', 'cart_rate', 'fav_rate', 'search_click_rate', 'bounce_rate', 'avg_stay_duration', 'ad_roi', 'repurchase_rate', 'cross_sell_rate', 'avg_order_value', 'industry_ctr', 'uv_value', 'search_conversion', 'click_rate']:
                    weekly_cols.append(func.avg(getattr(Model, col_name)).label(col_name))
                else:
                    weekly_cols.append(func.sum(getattr(Model, col_name)).label(col_name))
        base_cols.extend(weekly_cols)
    
    if dimension == 'monthly':
        monthly_cols = []
        for col_name in MONTHLY_ONLY_COLS:
            if hasattr(Model, col_name):
                if col_name in ['overall_roi', 'uv_value', 'search_ratio', 'click_rate', 'avg_order_value', 'paid_ratio', 'refund_paid_ratio', 'keyword_roi', 'crowd_roi', 'site_roi', 'keyword_ppc', 'crowd_ppc', 'site_ppc', 'industry_ctr', 'search_conversion', 'repurchase_rate', 'cross_sell_rate', 'new_buyer_ratio', 'score', 'ctr', 'cpc', 'cpm', 'click_conversion', 'presale_roi', 'item_fav_rate']:
                    monthly_cols.append(func.avg(getattr(Model, col_name)).label(col_name))
                else:
                    monthly_cols.append(func.sum(getattr(Model, col_name)).label(col_name))
        base_cols.extend(monthly_cols)
    
    query = db.query(*base_cols).join(Product, Model.product_id == Product.product_id)
    
    return query, Model, date_col, visitors_col


@router.get("", response_model=ResponseModel)
def get_products(
    dim: str = Query("weekly", alias="dim", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    tier: Optional[str] = Query(None, description="分层筛选"),
    style: Optional[str] = Query(None, description="风格筛选"),
    scene: Optional[str] = Query(None, description="场景筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    manager: Optional[str] = Query(None, description="负责人筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    category: Optional[str] = Query(None, description="类目筛选"),
    sort_by: str = Query("payment_amount", description="排序字段"),
    order: str = Query("desc", description="排序方向: asc/desc"),
    limit: int = Query(20, description="每页数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"data": [], "total": 0, "limit": limit, "offset": offset})
    
    query, _, _, _ = build_product_query(dim, period, db)
    filter_conditions = [getattr(Model, date_col) == period]
    
    if tier:
        filter_conditions.append(Product.tier == tier)
    if style:
        filter_conditions.append(Product.style == style)
    if scene:
        filter_conditions.append(Product.scene == scene)
    if manager:
        filter_conditions.append(Product.manager == manager)
    if category:
        filter_conditions.append(Product.category == category)
    if search:
        filter_conditions.append(
            Product.title.ilike(f"%{search}%") | Product.product_id.ilike(f"%{search}%")
        )
    if status:
        filter_conditions.append(Product.status == status)
    else:
        filter_conditions.append(Product.status == 'active')
    
    query = query.filter(*filter_conditions)
    query = query.group_by(Model.product_id)
    total = query.count()
    
    sort_col = sort_by if sort_by in SORT_WHITELIST else 'payment_amount'
    sort_dir = desc if order == "desc" else asc
    
    if sort_col == 'net_sales':
        query = query.order_by(sort_dir(
            func.sum(Model.payment_amount) - func.sum(Model.refund_amount)
        ))
    elif sort_col == 'refund_rate':
        query = query.order_by(sort_dir(
            func.sum(Model.refund_amount) / func.nullif(func.sum(Model.payment_amount), 0)
        ))
    elif sort_col == 'aov':
        query = query.order_by(sort_dir(
            func.sum(Model.payment_amount) / func.nullif(func.sum(getattr(Model, visitors_col)), 0)
        ))
    elif sort_col == 'ad_ratio':
        query = query.order_by(sort_dir(
            func.sum(Model.ad_spend) / func.nullif(func.sum(Model.payment_amount), 0)
        ))
    elif sort_col == 'visitors':
        query = query.order_by(sort_dir(func.sum(getattr(Model, visitors_col))))
    elif sort_col == 'conversion':
        query = query.order_by(sort_dir(func.avg(Model.payment_conversion)))
    elif sort_col == 'ad_spend':
        query = query.order_by(sort_dir(func.sum(Model.ad_spend)))
    elif sort_col == 'roi':
        query = query.order_by(sort_dir(func.avg(Model.ad_roi)))
    elif sort_col == 'title':
        query = query.order_by(sort_dir(func.lower(func.max(Product.title))))
    else:
        if hasattr(Model, sort_col):
            query = query.order_by(sort_dir(func.sum(getattr(Model, sort_col))))
        else:
            query = query.order_by(sort_dir(func.sum(Model.payment_amount)))
    
    products_data = query.offset(offset).limit(limit).all()
    
    product_ids = [p.product_id for p in products_data]
    prev_period = get_prev_period(str(period), dim)
    prev_data_map = {}
    
    if prev_period and product_ids:
        prev_query_cols = [
            Model.product_id,
            func.sum(Model.payment_amount).label('prev_payment'),
            func.sum(getattr(Model, visitors_col)).label('prev_visitors'),
            func.avg(Model.payment_conversion).label('prev_conversion'),
        ]
        if hasattr(Model, 'uv_value'):
            prev_query_cols.append(func.avg(Model.uv_value).label('prev_uv_value'))
        
        prev_query = db.query(*prev_query_cols).filter(
            getattr(Model, date_col) == prev_period,
            Model.product_id.in_(product_ids)
        ).group_by(Model.product_id)
        
        for p in prev_query.all():
            pd = {
                'payment_amount': float(p.prev_payment or 0),
                'visitors': int(p.prev_visitors or 0),
                'conversion': float(p.prev_conversion or 0),
            }
            if hasattr(p, 'prev_uv_value'):
                pd['uv_value'] = float(p.prev_uv_value or 0)
            prev_data_map[p.product_id] = pd
    
    products = []
    for p in products_data:
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        
        net_sales = payment - refund
        refund_rate = (refund / payment) if payment > 0 else 0
        aov = (payment / visitors) if visitors > 0 else 0
        ad_spend = float(p.ad_spend or 0)
        roi = float(p.roi or 0) if p.roi else 0
        conversion = float(p.conversion or 0)
        
        row_data = {
            'product_id': p.product_id,
            'title': p.title,
            'image_url': p.image_url,
            'category': p.category,
            'tier': p.tier,
            'style': p.style,
            'scene': p.scene,
            'manager': p.manager,
            'list_date': str(p.list_date) if p.list_date else None,
            'status': p.status,
            'starred': bool(p.starred) if p.starred is not None else False,
            'payment_amount': payment,
            'net_sales': net_sales,
            'refund_amount': refund,
            'refund_rate': refund_rate,
            'visitors': visitors,
            'aov': aov,
            'conversion': conversion,
            'ad_spend': ad_spend,
            'roi': roi,
            'payment_count': int(p.payment_count or 0),
            'order_count': int(getattr(p, 'order_count', 0) or 0),
            'ad_ratio': (ad_spend / payment) if payment > 0 else 0,
        }
        
        for col_name in ALL_COMMON_COLS:
            if hasattr(p, col_name):
                val = getattr(p, col_name)
                if val is not None:
                    row_data[col_name] = float(val) if isinstance(val, (int, float)) else val
        
        if dim == 'weekly':
            for col_name in WEEKLY_ONLY_COLS:
                if hasattr(p, col_name):
                    val = getattr(p, col_name)
                    if val is not None:
                        row_data[col_name] = float(val) if isinstance(val, (int, float)) else val
        
        if dim == 'monthly':
            for col_name in MONTHLY_ONLY_COLS:
                if hasattr(p, col_name):
                    val = getattr(p, col_name)
                    if val is not None:
                        row_data[col_name] = float(val) if isinstance(val, (int, float)) else val
            row_data['score'] = calc_score(row_data)
            
            prev_data = prev_data_map.get(p.product_id, {})
            if prev_data:
                changes = {}
                prev_payment = prev_data.get('payment_amount', 0)
                prev_visitors = prev_data.get('visitors', 0)
                prev_conversion = prev_data.get('conversion', 0)
                prev_uv = prev_data.get('uv_value', 0)
                
                if prev_payment > 0:
                    changes['payment_amount'] = round((payment - prev_payment) / prev_payment * 100, 1)
                if prev_visitors > 0:
                    changes['visitors'] = round((visitors - prev_visitors) / prev_visitors * 100, 1)
                if prev_conversion > 0:
                    changes['conversion'] = round((conversion - prev_conversion) / prev_conversion * 100, 1)
                if prev_uv and row_data.get('uv_value'):
                    changes['uv_value'] = round((row_data['uv_value'] - prev_uv) / prev_uv * 100, 1)
                if prev_payment > 0:
                    prev_refund_rate = prev_data.get('refund_amount', 0) / prev_payment
                    changes['refund_rate'] = round((refund_rate - prev_refund_rate) * 100, 1)
                
                row_data['changes'] = changes
            else:
                row_data['changes'] = {}
        else:
            row_data['score'] = calc_score(row_data)
            row_data['changes'] = {}
        
        products.append(row_data)
    
    return ResponseModel(data={
        "data": products,
        "total": total,
        "limit": limit,
        "offset": offset,
        "dimension": dim,
        "period": str(period) if period else None,
    })


@router.get("/ranking", response_model=ResponseModel)
def get_product_ranking(
    dim: str = Query("weekly", alias="dim", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    metric: str = Query("payment_amount", description="排名指标"),
    limit: int = Query(10, description="返回数量"),
    db: Session = Depends(get_db)
):
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"ranking": []})
    
    metric_map = {
        'payment_amount': func.sum(Model.payment_amount),
        'net_sales': func.sum(Model.payment_amount) - func.sum(Model.refund_amount),
        'visitors': func.sum(getattr(Model, visitors_col)),
        'conversion': func.avg(Model.payment_conversion),
        'roi': func.avg(Model.ad_roi),
        'refund_rate': func.sum(Model.refund_amount) / func.nullif(func.sum(Model.payment_amount), 0),
    }
    
    metric_func = metric_map.get(metric, metric_map['payment_amount'])
    
    ranking_query = db.query(
        Model.product_id,
        func.max(Product.title).label('product_name'),
        metric_func.label('metric_value')
    ).join(
        Product, Model.product_id == Product.product_id
    ).filter(
        getattr(Model, date_col) == period
    ).group_by(Model.product_id)
    
    ranking_data = ranking_query.order_by(desc('metric_value')).limit(limit).all()
    
    ranking = []
    for i, r in enumerate(ranking_data, 1):
        value = r.metric_value
        if metric == 'refund_rate' and value:
            value = float(value)
        elif value:
            value = float(value)
        
        ranking.append({
            "rank": i,
            "product_id": r.product_id,
            "product_name": r.product_name,
            "metric": metric,
            "value": round(value, 2) if value else 0
        })
    
    return ResponseModel(data={
        "ranking": ranking,
        "dimension": dim,
        "period": str(period) if period else None,
        "metric": metric
    })


@router.get("/top", response_model=ResponseModel)
def get_top_products(
    dim: str = Query("weekly", alias="dim", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    limit: int = Query(10, description="返回数量"),
    db: Session = Depends(get_db)
):
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"products": []})
    
    top_query = db.query(
        Model.product_id,
        func.max(Product.title).label('product_name'),
        func.max(Product.category).label('category'),
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).join(
        Product, Model.product_id == Product.product_id
    ).filter(
        getattr(Model, date_col) == period
    ).group_by(Model.product_id)
    
    top_products = top_query.order_by(desc(func.sum(Model.payment_amount))).limit(limit).all()
    
    products = []
    for p in top_products:
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        ad_spend = float(p.ad_spend or 0)
        
        products.append({
            "product_id": p.product_id,
            "product_name": p.product_name,
            "category": p.category,
            "payment_amount": round(payment, 2),
            "value": round(payment, 2),
            "net_sales": round(payment - refund, 2),
            "refund_amount": round(refund, 2),
            "refund_rate": round((refund / payment), 4) if payment > 0 else 0,
            "visitors": visitors,
            "aov": round((payment / visitors), 2) if visitors > 0 else 0,
            "conversion": round(float(p.conversion or 0), 4),
            "ad_spend": round(ad_spend, 2),
            "roi": round(float(p.roi or 0), 2) if p.roi else 0,
            "ad_ratio": round((ad_spend / payment), 4) if payment > 0 else 0,
        })
    
    return ResponseModel(data={
        "products": products,
        "dimension": dim,
        "period": str(period) if period else None
    })


@router.get("/categories", response_model=ResponseModel)
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Product.category).distinct().filter(Product.category.isnot(None)).all()
    tiers = db.query(Product.tier).distinct().filter(Product.tier.isnot(None)).all()
    styles = db.query(Product.style).distinct().filter(Product.style.isnot(None)).all()
    scenes = db.query(Product.scene).distinct().filter(Product.scene.isnot(None)).all()
    managers = db.query(Product.manager).distinct().filter(Product.manager.isnot(None)).all()
    
    return ResponseModel(data={
        "categories": [c[0] for c in categories if c[0]],
        "tiers": [t[0] for t in tiers if t[0]],
        "styles": [s[0] for s in styles if s[0]],
        "scenes": [s[0] for s in scenes if s[0]],
        "managers": [m[0] for m in managers if m[0]],
    })


@router.get("/{product_id}", response_model=ResponseModel)
def get_product_detail(
    product_id: str,
    dim: str = Query("weekly", alias="dim", description="时间维度"),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        return ResponseModel(data={"product": None, "trend": []})
    
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    data_list = db.query(Model).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    trend = []
    for model_data in reversed(data_list):
        period_val = None
        if date_col == 'month':
            period_val = model_data.month
        elif date_col == 'week_start':
            period_val = model_data.week_start.isoformat() if hasattr(model_data.week_start, 'isoformat') else str(model_data.week_start)
        else:
            period_val = model_data.date.isoformat() if hasattr(model_data.date, 'isoformat') else str(model_data.date)
        
        payment = model_data.payment_amount or 0
        refund = model_data.refund_amount or 0
        visitors = getattr(model_data, visitors_col) or 0
        
        item = {
            "period": period_val,
            "payment_amount": payment,
            "net_sales": payment - refund,
            "refund_amount": refund,
            "refund_rate": round((refund / payment), 4) if payment > 0 else 0,
            "visitors": visitors,
            "aov": round((payment / visitors), 2) if visitors > 0 else 0,
            "conversion": model_data.payment_conversion,
            "ad_spend": model_data.ad_spend or 0,
            "roi": model_data.ad_roi,
            "order_count": model_data.order_count or 0 if hasattr(model_data, 'order_count') else 0,
            "payment_count": model_data.payment_count or 0 if hasattr(model_data, 'payment_count') else 0,
        }
        for col_name in ALL_COMMON_COLS + MONTHLY_ONLY_COLS:
            if hasattr(model_data, col_name):
                val = getattr(model_data, col_name)
                if val is not None:
                    item[col_name] = val
        trend.append(item)
    
    return ResponseModel(data={
        "product_id": product.product_id,
        "product_name": product.title,
        "title": product.title,
        "image_url": product.image_url,
        "category": product.category,
        "tier": product.tier,
        "style": product.style,
        "scene": product.scene,
        "manager": product.manager,
        "list_date": str(product.list_date) if product.list_date else None,
        "status": product.status,
        "starred": bool(product.starred) if product.starred is not None else False,
        "trend": trend
    })


@router.patch("/{product_id}", response_model=ResponseModel)
def update_product_field(
    product_id: str,
    field: str = Body(..., embed=True),
    value: Any = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    valid_fields = ['tier', 'style', 'scene', 'manager', 'status', 'title', 'category']
    if field not in valid_fields:
        raise HTTPException(status_code=400, detail=f"不支持更新该字段: {field}")
    
    setattr(product, field, value)
    db.commit()
    db.refresh(product)
    
    return ResponseModel(data={"success": True, "product_id": product_id, "field": field, "value": value})


@router.post("/batch-update", response_model=ResponseModel)
def batch_update_products(
    product_ids: List[str] = Body(..., embed=True),
    tier: Optional[str] = Body(None, embed=True),
    style: Optional[str] = Body(None, embed=True),
    manager: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    products = db.query(Product).filter(Product.product_id.in_(product_ids)).all()
    updated = 0
    for product in products:
        if tier is not None:
            product.tier = tier
        if style is not None:
            product.style = style
        if manager is not None:
            product.manager = manager
        updated += 1
    
    db.commit()
    return ResponseModel(data={"success": True, "updated": updated, "total": len(product_ids)})


@router.get("/{product_id}/tags", response_model=ResponseModel)
def get_product_tags(product_id: str, db: Session = Depends(get_db)):
    tags = db.query(ProductTag).filter(ProductTag.product_id == product_id).all()
    return ResponseModel(data={"tags": [{"id": t.id, "tag": t.tag, "is_auto": t.is_auto} for t in tags]})


@router.post("/{product_id}/tags", response_model=ResponseModel)
def add_product_tag(
    product_id: str,
    tag: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    new_tag = ProductTag(product_id=product_id, tag=tag, is_auto=False)
    db.add(new_tag)
    db.commit()
    return ResponseModel(data={"success": True, "tag_id": new_tag.id})


@router.delete("/{product_id}/tags/{tag_id}", response_model=ResponseModel)
def delete_product_tag(
    product_id: str,
    tag_id: int,
    db: Session = Depends(get_db)
):
    tag = db.query(ProductTag).filter(ProductTag.id == tag_id, ProductTag.product_id == product_id).first()
    if tag:
        db.delete(tag)
        db.commit()
    return ResponseModel(data={"success": True})


@router.get("/{product_id}/notes", response_model=ResponseModel)
def get_product_notes(product_id: str, db: Session = Depends(get_db)):
    notes = db.query(ProductNote).filter(ProductNote.product_id == product_id).order_by(desc(ProductNote.created_at)).all()
    return ResponseModel(data={"notes": [{"id": n.id, "note": n.note, "created_by": n.created_by, "created_at": str(n.created_at)} for n in notes]})


@router.post("/{product_id}/notes", response_model=ResponseModel)
def add_product_note(
    product_id: str,
    note: str = Body(..., embed=True),
    created_by: str = Body("admin", embed=True),
    db: Session = Depends(get_db)
):
    new_note = ProductNote(product_id=product_id, note=note, created_by=created_by)
    db.add(new_note)
    db.commit()
    return ResponseModel(data={"success": True, "note_id": new_note.id})


@router.get("/{product_id}/weekly-data", response_model=ResponseModel)
def get_product_weekly_data(product_id: str, db: Session = Depends(get_db)):
    data_list = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id
    ).order_by(desc(WeeklyData.week_start)).limit(12).all()
    
    result = []
    for model_data in data_list:
        payment = model_data.payment_amount or 0
        refund = model_data.refund_amount or 0
        visitors = model_data.ipv or 0
        
        item = {
            "week_start": model_data.week_start.isoformat() if hasattr(model_data.week_start, 'isoformat') else str(model_data.week_start),
            "payment_amount": payment,
            "net_sales": payment - refund,
            "refund_amount": refund,
            "refund_rate": round((refund / payment), 4) if payment > 0 else 0,
            "visitors": visitors,
            "ipv": visitors,
            "aov": round((payment / visitors), 2) if visitors > 0 else 0,
            "payment_conversion": model_data.payment_conversion,
            "ad_spend": model_data.ad_spend or 0,
            "ad_roi": model_data.ad_roi,
            "total_roi": model_data.ad_roi,
            "order_count": model_data.order_count or 0 if hasattr(model_data, 'order_count') else 0,
            "presale_qty": model_data.presale_qty or 0,
        }
        for col_name in ALL_COMMON_COLS + MONTHLY_ONLY_COLS:
            if hasattr(model_data, col_name):
                val = getattr(model_data, col_name)
                if val is not None:
                    item[col_name] = val
        result.append(item)
    
    return ResponseModel(data=result)


@router.get("/{product_id}/operations", response_model=ResponseModel)
def get_product_operations(product_id: str, db: Session = Depends(get_db)):
    actions = db.query(OperationAction).filter(
        OperationAction.product_id == product_id
    ).order_by(desc(OperationAction.id)).limit(50).all()
    
    return ResponseModel(data={
        "actions": [{
            "id": a.id,
            "product_id": a.product_id,
            "action_date": str(a.action_date),
            "action_type": a.action_type,
            "action_detail": a.action_detail,
            "before_payment": a.before_payment,
            "before_visitors": a.before_visitors,
            "before_conversion": a.before_conversion,
            "before_roi": a.before_roi,
            "after_payment": a.after_payment,
            "after_visitors": a.after_visitors,
            "after_conversion": a.after_conversion,
            "after_roi": a.after_roi,
        } for a in actions]
    })


@router.delete("/{product_id}/notes/{note_id}", response_model=ResponseModel)
def delete_product_note(
    product_id: str,
    note_id: int,
    db: Session = Depends(get_db)
):
    note = db.query(ProductNote).filter(ProductNote.id == note_id, ProductNote.product_id == product_id).first()
    if note:
        db.delete(note)
        db.commit()
    return ResponseModel(data={"success": True})


@router.post("/actions", response_model=ResponseModel)
def create_action(
    product_id: str = Body(..., embed=True),
    action_date: str = Body(..., embed=True),
    action_type: Optional[str] = Body(None, embed=True),
    action_detail: Optional[str] = Body(None, embed=True),
    before_payment: Optional[float] = Body(0, embed=True),
    before_visitors: Optional[int] = Body(0, embed=True),
    before_conversion: Optional[float] = Body(0, embed=True),
    before_roi: Optional[float] = Body(0, embed=True),
    after_payment: Optional[float] = Body(0, embed=True),
    after_visitors: Optional[int] = Body(0, embed=True),
    after_conversion: Optional[float] = Body(0, embed=True),
    after_roi: Optional[float] = Body(0, embed=True),
    db: Session = Depends(get_db)
):
    new_action = OperationAction(
        product_id=product_id,
        action_date=action_date,
        action_type=action_type,
        action_detail=action_detail,
        before_payment=before_payment,
        before_visitors=before_visitors,
        before_conversion=before_conversion,
        before_roi=before_roi,
        after_payment=after_payment,
        after_visitors=after_visitors,
        after_conversion=after_conversion,
        after_roi=after_roi,
    )
    db.add(new_action)
    db.commit()
    db.refresh(new_action)
    
    return ResponseModel(data={"success": True, "id": new_action.id})
