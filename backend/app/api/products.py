from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, case, text
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

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

MONTHLY_ONLY_COLS = [
    'overall_roi', 'paid_ratio', 'refund_paid_ratio',
    'keyword_spend', 'keyword_sales', 'keyword_roi', 'keyword_visitors', 'keyword_ppc',
    'crowd_spend', 'crowd_sales', 'crowd_roi', 'crowd_visitors', 'crowd_ppc',
    'site_spend', 'site_sales', 'site_roi', 'site_visitors', 'site_ppc',
    'paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv',
    'industry_ctr', 'cross_sell_qty', 'cross_sell_categories',
    'repurchase_rate', 'cross_sell_rate',
    'uv_value', 'search_visitors', 'search_ratio', 'search_conversion',
    'cart_qty', 'fav_users', 'click_rate', 'score',
    'cart_users', 'new_buyers', 'new_buyer_ratio',
]


def get_latest_period(Model, date_col, db):
    """获取最新周期"""
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        return getattr(latest, date_col)
    return None


def calc_score(row_data: dict) -> float:
    """计算商品综合评分（0-100分）- 兼容老版本算法"""
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
    """获取上一个周期"""
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
    """构建商品查询基础query"""
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
        func.max(Product.title).label('product_name'),
        func.max(Product.category).label('category'),
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
        func.sum(Model.order_count).label('order_count'),
        func.sum(Model.payment_count).label('payment_count'),
    ]
    
    if dimension == 'monthly':
        monthly_cols = [
            func.avg(Model.overall_roi).label('overall_roi'),
            func.avg(Model.uv_value).label('uv_value'),
            func.avg(Model.search_ratio).label('search_ratio'),
            func.avg(Model.click_rate).label('click_rate'),
            func.sum(Model.buyers).label('buyers'),
            func.avg(Model.avg_order_value).label('avg_order_value'),
            func.sum(Model.net_sales).label('net_sales'),
        ]
        base_cols.extend(monthly_cols)
    
    query = db.query(*base_cols).join(Product, Model.product_id == Product.product_id)
    
    return query, Model, date_col, visitors_col


@router.get("", response_model=ResponseModel)
def get_products(
    dim: str = Query("weekly", alias="dim", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    tier: Optional[str] = Query(None, description="分层筛选"),
    style: Optional[str] = Query(None, description="风格筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    status: Optional[str] = Query(None, description="状态筛选"),
    sort_by: str = Query("payment_amount", description="排序字段"),
    order: str = Query("desc", description="排序方向: asc/desc"),
    limit: int = Query(20, description="每页数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取商品列表（兼容老版本API）"""
    
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
    elif sort_col == 'roi':
        query = query.order_by(sort_dir(func.avg(Model.ad_roi)))
    elif sort_col == 'title':
        query = query.order_by(sort_dir(func.lower(Model.product_name)))
    else:
        if hasattr(Model, sort_col):
            query = query.order_by(sort_dir(func.sum(getattr(Model, sort_col))))
        else:
            query = query.order_by(sort_dir(func.sum(Model.payment_amount)))
    
    products_data = query.offset(offset).limit(limit).all()
    
    product_ids = [p.product_id for p in products_data]
    prev_period = get_prev_period(str(period), dim)
    prev_data_map = {}
    
    if prev_period and product_ids and dim == 'monthly':
        prev_query = db.query(
            Model.product_id,
            func.sum(Model.payment_amount).label('prev_payment'),
            func.sum(getattr(Model, visitors_col)).label('prev_visitors'),
            func.avg(Model.payment_conversion).label('prev_conversion'),
            func.avg(Model.uv_value).label('prev_uv_value'),
        ).filter(
            getattr(Model, date_col) == prev_period,
            Model.product_id.in_(product_ids)
        )
        
        if hasattr(Model, 'product_name'):
            prev_query = prev_query.group_by(Model.product_id, Model.product_name, Model.category)
        else:
            prev_query = prev_query.group_by(Model.product_id)
        
        for p in prev_query.all():
            prev_data_map[p.product_id] = {
                'payment_amount': float(p.prev_payment or 0),
                'visitors': int(p.prev_visitors or 0),
                'conversion': float(p.prev_conversion or 0),
                'uv_value': float(p.prev_uv_value or 0),
            }
    
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
            'title': p.product_name,
            'category': p.category,
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
            'order_count': int(p.order_count or 0),
        }
        
        if dim == 'monthly':
            row_data.update({
                'overall_roi': float(p.overall_roi or 0) if hasattr(p, 'overall_roi') else 0,
                'uv_value': float(p.uv_value or 0) if hasattr(p, 'uv_value') else 0,
                'search_ratio': float(p.search_ratio or 0) if hasattr(p, 'search_ratio') else 0,
                'click_rate': float(p.click_rate or 0) if hasattr(p, 'click_rate') else 0,
                'buyers': int(p.buyers or 0) if hasattr(p, 'buyers') else 0,
                'avg_order_value': float(p.avg_order_value or 0) if hasattr(p, 'avg_order_value') else 0,
            })
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
                if prev_uv > 0:
                    changes['uv_value'] = round((row_data['uv_value'] - prev_uv) / prev_uv * 100, 1)
                changes['refund_rate'] = round((refund_rate - (prev_data.get('refund_amount', 0) / prev_payment if prev_payment > 0 else 0)) * 100, 1) if prev_payment > 0 else None
                
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
    """获取商品排名"""
    
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
    """获取TOP商品列表"""
    
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
    """获取所有商品类目"""
    categories = db.query(Product.category).distinct().filter(Product.category.isnot(None)).all()
    return ResponseModel(data={
        "categories": [c[0] for c in categories if c[0]]
    })


@router.get("/{product_id}", response_model=ResponseModel)
def get_product_detail(
    product_id: str,
    dim: str = Query("weekly", alias="dim", description="时间维度"),
    db: Session = Depends(get_db)
):
    """获取商品详情"""
    
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    data_list = db.query(Model, Product.title, Product.category).join(
        Product, Model.product_id == Product.product_id
    ).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    if not data_list:
        return ResponseModel(data={"product": None, "trend": []})
    
    product_info = data_list[0]
    product_name = product_info[1]
    product_category = product_info[2]
    trend = []
    for data_record in reversed(data_list):
        model_data = data_record[0]
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
        
        trend.append({
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
            "order_count": model_data.order_count or 0,
            "payment_count": model_data.payment_count or 0,
        })
    
    return ResponseModel(data={
        "product": {
            "product_id": product_id,
            "product_name": product_name,
            "category": product_category,
            "trend": trend
        },
        "dimension": dim
    })
