from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.models import TrafficSource, ProductTrafficDetail, CategoryData, StoreDailyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/sycm", tags=["生意参谋数据"])


@router.get("/traffic-sources/summary", response_model=ResponseModel)
def get_traffic_sources_summary(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    source_type: Optional[str] = Query(None, description="流量类型"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取流量来源汇总数据"""
    query = db.query(TrafficSource)
    
    if start_date:
        query = query.filter(TrafficSource.date >= start_date)
    if end_date:
        query = query.filter(TrafficSource.date <= end_date)
    if source_type:
        query = query.filter(TrafficSource.source_type == source_type)
    if product_id:
        query = query.filter(TrafficSource.product_id == product_id)
    
    summary = db.query(
        func.sum(TrafficSource.visitors).label('total_visitors'),
        func.sum(TrafficSource.payment_amount).label('total_payment'),
        func.sum(TrafficSource.payment_buyers).label('total_buyers'),
        func.sum(TrafficSource.page_views).label('total_pv'),
        func.avg(TrafficSource.conversion_rate).label('avg_conversion'),
        func.avg(TrafficSource.uv_value).label('avg_uv_value'),
    ).select_from(query.subquery()).first()
    
    source_breakdown = db.query(
        TrafficSource.source_name,
        TrafficSource.source_type,
        func.sum(TrafficSource.visitors).label('visitors'),
        func.sum(TrafficSource.payment_amount).label('payment_amount'),
        func.sum(TrafficSource.payment_buyers).label('payment_buyers'),
        func.avg(TrafficSource.conversion_rate).label('conversion_rate'),
        func.avg(TrafficSource.uv_value).label('uv_value'),
        func.sum(TrafficSource.new_visitors).label('new_visitors'),
        func.sum(TrafficSource.cart_users).label('cart_users'),
        func.sum(TrafficSource.favorite_users).label('favorite_users'),
    ).filter(
        and_(
            TrafficSource.date >= (start_date or "2000-01-01"),
            TrafficSource.date <= (end_date or "2099-12-31"),
        ),
        TrafficSource.source_type == source_type if source_type else True,
        TrafficSource.product_id == product_id if product_id else True,
    ).group_by(
        TrafficSource.source_name, TrafficSource.source_type
    ).order_by(desc(func.sum(TrafficSource.visitors))).limit(limit).all()
    
    total_visitors = sum(s.visitors for s in source_breakdown)
    
    sources = []
    for s in source_breakdown:
        sources.append({
            "source_name": s.source_name,
            "source_type": s.source_type,
            "visitors": s.visitors or 0,
            "visitor_pct": round((s.visitors / total_visitors * 100), 1) if total_visitors > 0 else 0,
            "payment_amount": round(s.payment_amount or 0, 2),
            "payment_buyers": s.payment_buyers or 0,
            "conversion_rate": round((s.conversion_rate or 0) * 100, 2),
            "uv_value": round(s.uv_value or 0, 2),
            "new_visitors": s.new_visitors or 0,
            "cart_users": s.cart_users or 0,
            "favorite_users": s.favorite_users or 0,
        })
    
    kpi = {
        "total_visitors": summary.total_visitors or 0,
        "total_payment": round(summary.total_payment or 0, 2),
        "total_buyers": summary.total_buyers or 0,
        "total_pv": summary.total_pv or 0,
        "avg_conversion": round((summary.avg_conversion or 0) * 100, 2),
        "avg_uv_value": round(summary.avg_uv_value or 0, 2),
    }
    
    return ResponseModel(data={
        "kpi": kpi,
        "sources": sources,
        "period": f"{start_date or '全部'} ~ {end_date or '全部'}",
    })


@router.get("/traffic-sources/trend", response_model=ResponseModel)
def get_traffic_sources_trend(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    source_name: Optional[str] = Query(None, description="来源名称"),
    db: Session = Depends(get_db)
):
    """获取流量来源趋势数据"""
    query = db.query(
        TrafficSource.date,
        func.sum(TrafficSource.visitors).label('visitors'),
        func.sum(TrafficSource.payment_amount).label('payment_amount'),
        func.sum(TrafficSource.payment_buyers).label('payment_buyers'),
        func.avg(TrafficSource.conversion_rate).label('conversion_rate'),
    ).filter(
        TrafficSource.date >= (start_date or "2000-01-01"),
        TrafficSource.date <= (end_date or "2099-12-31"),
    )
    
    if source_name:
        query = query.filter(TrafficSource.source_name == source_name)
    
    trends = query.group_by(TrafficSource.date).order_by(TrafficSource.date).all()
    
    result = []
    for t in trends:
        result.append({
            "date": t.date,
            "visitors": t.visitors or 0,
            "payment_amount": round(t.payment_amount or 0, 2),
            "payment_buyers": t.payment_buyers or 0,
            "conversion_rate": round((t.conversion_rate or 0) * 100, 2),
        })
    
    return ResponseModel(data={"trends": result})


@router.get("/product-traffic/summary", response_model=ResponseModel)
def get_product_traffic_summary(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    limit: int = Query(50, description="返回数量"),
    sort_by: str = Query("payment_amount", description="排序字段"),
    db: Session = Depends(get_db)
):
    """获取商品流量+广告汇总数据"""
    query = db.query(ProductTrafficDetail).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
    )
    
    if product_id:
        query = query.filter(ProductTrafficDetail.product_id == product_id)
    
    sort_map = {
        "payment_amount": func.sum(ProductTrafficDetail.payment_amount),
        "visitors": func.sum(ProductTrafficDetail.visitors),
        "ad_spend": func.sum(ProductTrafficDetail.ad_spend),
        "ad_roi": func.avg(ProductTrafficDetail.ad_roi),
        "conversion_rate": func.avg(ProductTrafficDetail.conversion_rate),
        "search_visitors": func.sum(ProductTrafficDetail.search_visitors),
        "recommend_visitors": func.sum(ProductTrafficDetail.recommend_visitors),
    }
    sort_col = sort_map.get(sort_by, sort_map["payment_amount"])
    
    products = query.group_by(
        ProductTrafficDetail.product_id,
        ProductTrafficDetail.store_name,
    ).add_columns(
        Product.title,
        func.sum(ProductTrafficDetail.payment_amount).label('payment_amount'),
        func.sum(ProductTrafficDetail.payment_items).label('payment_items'),
        func.sum(ProductTrafficDetail.payment_buyers).label('payment_buyers'),
        func.sum(ProductTrafficDetail.visitors).label('visitors'),
        func.sum(ProductTrafficDetail.page_views).label('page_views'),
        func.avg(ProductTrafficDetail.conversion_rate).label('conversion_rate'),
        func.avg(ProductTrafficDetail.aov).label('aov'),
        func.avg(ProductTrafficDetail.uv_value).label('uv_value'),
        func.sum(ProductTrafficDetail.ad_spend).label('ad_spend'),
        func.avg(ProductTrafficDetail.ad_roi).label('ad_roi'),
        func.sum(ProductTrafficDetail.search_visitors).label('search_visitors'),
        func.sum(ProductTrafficDetail.recommend_visitors).label('recommend_visitors'),
        func.sum(ProductTrafficDetail.keyword_ad_spend).label('keyword_ad_spend'),
        func.avg(ProductTrafficDetail.keyword_ad_roi).label('keyword_ad_roi'),
        func.sum(ProductTrafficDetail.audience_ad_spend).label('audience_ad_spend'),
        func.avg(ProductTrafficDetail.audience_ad_roi).label('audience_ad_roi'),
        func.sum(ProductTrafficDetail.scene_ad_spend).label('scene_ad_spend'),
        func.avg(ProductTrafficDetail.scene_ad_roi).label('scene_ad_roi'),
        func.sum(ProductTrafficDetail.full_site_ad_spend).label('full_site_ad_spend'),
        func.avg(ProductTrafficDetail.full_site_ad_roi).label('full_site_ad_roi'),
    ).outerjoin(
        Product, ProductTrafficDetail.product_id == Product.product_id
    ).order_by(desc(sort_col)).limit(limit).all()
    
    result = []
    for p in products:
        traffic_detail, title = p[0], p[1]
        result.append({
            "product_id": traffic_detail.product_id,
            "title": title,
            "payment_amount": round(p.payment_amount or 0, 2),
            "payment_items": p.payment_items or 0,
            "payment_buyers": p.payment_buyers or 0,
            "visitors": p.visitors or 0,
            "page_views": p.page_views or 0,
            "conversion_rate": round((p.conversion_rate or 0) * 100, 2),
            "aov": round(p.aov or 0, 2),
            "uv_value": round(p.uv_value or 0, 2),
            "ad_spend": round(p.ad_spend or 0, 2),
            "ad_roi": round(p.ad_roi or 0, 2),
            "ad_ratio": round((p.ad_spend / p.payment_amount * 100) if p.payment_amount and p.payment_amount > 0 else 0, 2),
            "search_visitors": p.search_visitors or 0,
            "recommend_visitors": p.recommend_visitors or 0,
            "search_payment": round(getattr(traffic_detail, 'search_payment_amount', 0) or 0, 2),
            "recommend_payment": round(getattr(traffic_detail, 'recommend_payment_amount', 0) or 0, 2),
            "ad_breakdown": {
                "keyword": {"spend": round(p.keyword_ad_spend or 0, 2), "roi": round(p.keyword_ad_roi or 0, 2)},
                "audience": {"spend": round(p.audience_ad_spend or 0, 2), "roi": round(p.audience_ad_roi or 0, 2)},
                "scene": {"spend": round(p.scene_ad_spend or 0, 2), "roi": round(p.scene_ad_roi or 0, 2)},
                "full_site": {"spend": round(p.full_site_ad_spend or 0, 2), "roi": round(p.full_site_ad_roi or 0, 2)},
            },
        })
    
    overall = db.query(
        func.sum(ProductTrafficDetail.payment_amount).label('payment_amount'),
        func.sum(ProductTrafficDetail.visitors).label('visitors'),
        func.sum(ProductTrafficDetail.ad_spend).label('ad_spend'),
        func.avg(ProductTrafficDetail.ad_roi).label('ad_roi'),
    ).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
        ProductTrafficDetail.product_id == product_id if product_id else True,
    ).first()
    
    return ResponseModel(data={
        "products": result,
        "overall": {
            "payment_amount": round(overall.payment_amount or 0, 2),
            "visitors": overall.visitors or 0,
            "ad_spend": round(overall.ad_spend or 0, 2),
            "ad_roi": round(overall.ad_roi or 0, 2),
        },
        "period": f"{start_date or '全部'} ~ {end_date or '全部'}",
    })


@router.get("/product-traffic/trend", response_model=ResponseModel)
def get_product_traffic_trend(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    db: Session = Depends(get_db)
):
    """获取商品流量趋势数据"""
    query = db.query(
        ProductTrafficDetail.date,
        func.sum(ProductTrafficDetail.payment_amount).label('payment_amount'),
        func.sum(ProductTrafficDetail.visitors).label('visitors'),
        func.sum(ProductTrafficDetail.ad_spend).label('ad_spend'),
        func.avg(ProductTrafficDetail.ad_roi).label('ad_roi'),
        func.sum(ProductTrafficDetail.search_visitors).label('search_visitors'),
        func.sum(ProductTrafficDetail.recommend_visitors).label('recommend_visitors'),
        func.sum(ProductTrafficDetail.keyword_ad_spend).label('keyword_ad_spend'),
        func.sum(ProductTrafficDetail.audience_ad_spend).label('audience_ad_spend'),
        func.sum(ProductTrafficDetail.scene_ad_spend).label('scene_ad_spend'),
        func.sum(ProductTrafficDetail.full_site_ad_spend).label('full_site_ad_spend'),
    ).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
    )
    
    if product_id:
        query = query.filter(ProductTrafficDetail.product_id == product_id)
    
    trends = query.group_by(ProductTrafficDetail.date).order_by(ProductTrafficDetail.date).all()
    
    result = []
    for t in trends:
        total_ad = (t.keyword_ad_spend or 0) + (t.audience_ad_spend or 0) + (t.scene_ad_spend or 0) + (t.full_site_ad_spend or 0)
        result.append({
            "date": t.date,
            "payment_amount": round(t.payment_amount or 0, 2),
            "visitors": t.visitors or 0,
            "ad_spend": round(t.ad_spend or 0, 2),
            "ad_roi": round(t.ad_roi or 0, 2),
            "search_visitors": t.search_visitors or 0,
            "recommend_visitors": t.recommend_visitors or 0,
            "ad_breakdown": {
                "keyword": round(t.keyword_ad_spend or 0, 2),
                "audience": round(t.audience_ad_spend or 0, 2),
                "scene": round(t.scene_ad_spend or 0, 2),
                "full_site": round(t.full_site_ad_spend or 0, 2),
                "total": round(total_ad, 2),
            },
        })
    
    return ResponseModel(data={"trends": result})


@router.get("/product-traffic/detail", response_model=ResponseModel)
def get_product_traffic_detail(
    product_id: str = Query(..., description="商品ID"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """获取单个商品的流量+广告每日明细"""
    query = db.query(ProductTrafficDetail).filter(
        ProductTrafficDetail.product_id == product_id,
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
    ).order_by(ProductTrafficDetail.date).all()
    
    product_info = db.query(Product).filter(Product.product_id == product_id).first()
    
    result = []
    for d in query:
        result.append({
            "date": d.date,
            "payment_amount": round(d.payment_amount or 0, 2),
            "payment_items": d.payment_items or 0,
            "payment_buyers": d.payment_buyers or 0,
            "visitors": d.visitors or 0,
            "page_views": d.page_views or 0,
            "conversion_rate": round((d.conversion_rate or 0) * 100, 2),
            "aov": round(d.aov or 0, 2),
            "uv_value": round(d.uv_value or 0, 2),
            "search_visitors": d.search_visitors or 0,
            "search_cart_users": d.search_cart_users or 0,
            "search_payment_amount": round(d.search_payment_amount or 0, 2),
            "recommend_visitors": d.recommend_visitors or 0,
            "recommend_cart_users": d.recommend_cart_users or 0,
            "recommend_payment_amount": round(d.recommend_payment_amount or 0, 2),
            "ad_spend": round(d.ad_spend or 0, 2),
            "ad_roi": round(d.ad_roi or 0, 2),
            "ad_traffic": d.ad_traffic or 0,
            "ad_traffic_ratio": round(d.ad_traffic_ratio or 0, 2),
            "platform_traffic": d.platform_traffic or 0,
            "platform_traffic_ratio": round(d.platform_traffic_ratio or 0, 2),
            "keyword_ad": {
                "spend": round(d.keyword_ad_spend or 0, 2),
                "roi": round(d.keyword_ad_roi or 0, 2),
                "visitors": d.keyword_ad_visitors or 0,
                "cart_users": d.keyword_ad_cart_users or 0,
                "sales": round(d.keyword_ad_sales or 0, 2),
                "orders": d.keyword_ad_orders or 0,
                "cvr": round((d.keyword_ad_cvr or 0) * 100, 2),
            },
            "audience_ad": {
                "spend": round(d.audience_ad_spend or 0, 2),
                "roi": round(d.audience_ad_roi or 0, 2),
                "visitors": d.audience_ad_visitors or 0,
                "cart_users": d.audience_ad_cart_users or 0,
                "sales": round(d.audience_ad_sales or 0, 2),
                "orders": d.audience_ad_orders or 0,
                "cvr": round((d.audience_ad_cvr or 0) * 100, 2),
            },
            "scene_ad": {
                "spend": round(d.scene_ad_spend or 0, 2),
                "roi": round(d.scene_ad_roi or 0, 2),
                "visitors": d.scene_ad_visitors or 0,
                "cart_users": d.scene_ad_cart_users or 0,
                "sales": round(d.scene_ad_sales or 0, 2),
                "orders": d.scene_ad_orders or 0,
                "cvr": round((d.scene_ad_cvr or 0) * 100, 2),
            },
            "full_site_ad": {
                "spend": round(d.full_site_ad_spend or 0, 2),
                "roi": round(d.full_site_ad_roi or 0, 2),
                "visitors": d.full_site_ad_visitors or 0,
                "cart_users": d.full_site_ad_cart_users or 0,
                "sales": round(d.full_site_ad_sales or 0, 2),
                "orders": d.full_site_ad_orders or 0,
                "cvr": round((d.full_site_ad_cvr or 0) * 100, 2),
            },
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "product_name": product_info.title if product_info else "",
        "daily_data": result,
    })


@router.get("/category/summary", response_model=ResponseModel)
def get_category_summary(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    category_name: Optional[str] = Query(None, description="品类名称"),
    limit: int = Query(30, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取品类汇总数据"""
    query = db.query(
        CategoryData.category_name,
        CategoryData.level1_category,
        CategoryData.level2_category,
        func.sum(CategoryData.payment_amount).label('payment_amount'),
        func.sum(CategoryData.visitors).label('visitors'),
        func.sum(CategoryData.payment_buyers).label('payment_buyers'),
        func.avg(CategoryData.payment_conversion).label('payment_conversion'),
        func.avg(CategoryData.uv_value).label('uv_value'),
        func.sum(CategoryData.cart_users).label('cart_users'),
        func.sum(CategoryData.favorite_users).label('favorite_users'),
        func.sum(CategoryData.favorite_conversion).label('favorite_conversion'),
        func.sum(CategoryData.cart_conversion).label('cart_conversion'),
    ).filter(
        CategoryData.date >= (start_date or "2000-01-01"),
        CategoryData.date <= (end_date or "2099-12-31"),
    )
    
    if category_name:
        query = query.filter(CategoryData.category_name == category_name)
    
    categories = query.group_by(
        CategoryData.category_name,
        CategoryData.level1_category,
        CategoryData.level2_category,
    ).order_by(desc(func.sum(CategoryData.payment_amount))).limit(limit).all()
    
    result = []
    for c in categories:
        result.append({
            "category_name": c.category_name,
            "level1_category": c.level1_category,
            "level2_category": c.level2_category,
            "payment_amount": round(c.payment_amount or 0, 2),
            "visitors": c.visitors or 0,
            "payment_buyers": c.payment_buyers or 0,
            "payment_conversion": round((c.payment_conversion or 0) * 100, 2),
            "uv_value": round(c.uv_value or 0, 2),
            "cart_users": c.cart_users or 0,
            "favorite_users": c.favorite_users or 0,
            "cart_conversion": round((c.cart_conversion or 0) * 100, 2),
            "favorite_conversion": round((c.favorite_conversion or 0) * 100, 2),
        })
    
    overall = db.query(
        func.sum(CategoryData.payment_amount).label('payment_amount'),
        func.sum(CategoryData.visitors).label('visitors'),
        func.sum(CategoryData.payment_buyers).label('payment_buyers'),
    ).filter(
        CategoryData.date >= (start_date or "2000-01-01"),
        CategoryData.date <= (end_date or "2099-12-31"),
    ).first()
    
    return ResponseModel(data={
        "categories": result,
        "overall": {
            "payment_amount": round(overall.payment_amount or 0, 2),
            "visitors": overall.visitors or 0,
            "payment_buyers": overall.payment_buyers or 0,
        },
        "period": f"{start_date or '全部'} ~ {end_date or '全部'}",
    })


@router.get("/category/trend", response_model=ResponseModel)
def get_category_trend(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    category_name: Optional[str] = Query(None, description="品类名称"),
    db: Session = Depends(get_db)
):
    """获取品类趋势数据"""
    query = db.query(
        CategoryData.date,
        func.sum(CategoryData.payment_amount).label('payment_amount'),
        func.sum(CategoryData.visitors).label('visitors'),
        func.sum(CategoryData.payment_buyers).label('payment_buyers'),
        func.avg(CategoryData.payment_conversion).label('payment_conversion'),
    ).filter(
        CategoryData.date >= (start_date or "2000-01-01"),
        CategoryData.date <= (end_date or "2099-12-31"),
    )
    
    if category_name:
        query = query.filter(CategoryData.category_name == category_name)
    
    trends = query.group_by(CategoryData.date).order_by(CategoryData.date).all()
    
    result = []
    for t in trends:
        result.append({
            "date": t.date,
            "payment_amount": round(t.payment_amount or 0, 2),
            "visitors": t.visitors or 0,
            "payment_buyers": t.payment_buyers or 0,
            "payment_conversion": round((t.payment_conversion or 0) * 100, 2),
        })
    
    return ResponseModel(data={"trends": result})


@router.get("/store-daily/summary", response_model=ResponseModel)
def get_store_daily_summary(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """获取店铺日报汇总数据"""
    query = db.query(StoreDailyData).filter(
        StoreDailyData.date >= (start_date or "2000-01-01"),
        StoreDailyData.date <= (end_date or "2099-12-31"),
    )
    
    summary = db.query(
        func.sum(StoreDailyData.visitors).label('total_visitors'),
        func.sum(StoreDailyData.payment_amount).label('total_payment'),
        func.sum(StoreDailyData.payment_buyers).label('total_buyers'),
        func.sum(StoreDailyData.page_views).label('total_pv'),
        func.sum(StoreDailyData.followers).label('total_followers'),
        func.avg(StoreDailyData.conversion_rate).label('avg_conversion'),
        func.avg(StoreDailyData.uv_value).label('avg_uv_value'),
        func.avg(StoreDailyData.aov).label('avg_aov'),
    ).select_from(query.subquery()).first()
    
    return ResponseModel(data={
        "kpi": {
            "total_visitors": summary.total_visitors or 0,
            "total_payment": round(summary.total_payment or 0, 2),
            "total_buyers": summary.total_buyers or 0,
            "total_pv": summary.total_pv or 0,
            "total_followers": summary.total_followers or 0,
            "avg_conversion": round((summary.avg_conversion or 0) * 100, 2),
            "avg_uv_value": round(summary.avg_uv_value or 0, 2),
            "avg_aov": round(summary.avg_aov or 0, 2),
        },
        "period": f"{start_date or '全部'} ~ {end_date or '全部'}",
    })


@router.get("/store-daily/trend", response_model=ResponseModel)
def get_store_daily_trend(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """获取店铺日报趋势数据"""
    trends = db.query(
        StoreDailyData.date,
        StoreDailyData.visitors,
        StoreDailyData.new_visitors,
        StoreDailyData.page_views,
        StoreDailyData.payment_buyers,
        StoreDailyData.payment_amount,
        StoreDailyData.followers,
        StoreDailyData.favorite_users,
        StoreDailyData.cart_users,
        StoreDailyData.cart_items,
        StoreDailyData.conversion_rate,
        StoreDailyData.uv_value,
        StoreDailyData.aov,
        StoreDailyData.avg_stay_duration,
    ).filter(
        StoreDailyData.date >= (start_date or "2000-01-01"),
        StoreDailyData.date <= (end_date or "2099-12-31"),
    ).order_by(StoreDailyData.date).all()
    
    result = []
    for t in trends:
        result.append({
            "date": t.date,
            "visitors": t.visitors or 0,
            "new_visitors": t.new_visitors or 0,
            "page_views": t.page_views or 0,
            "payment_buyers": t.payment_buyers or 0,
            "payment_amount": round(t.payment_amount or 0, 2),
            "followers": t.followers or 0,
            "favorite_users": t.favorite_users or 0,
            "cart_users": t.cart_users or 0,
            "cart_items": t.cart_items or 0,
            "conversion_rate": round((t.conversion_rate or 0) * 100, 2),
            "uv_value": round(t.uv_value or 0, 2),
            "aov": round(t.aov or 0, 2),
            "avg_stay_duration": round(t.avg_stay_duration or 0, 2),
        })
    
    return ResponseModel(data={"trends": result})


@router.get("/ad/overview", response_model=ResponseModel)
def get_ad_overview(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    db: Session = Depends(get_db)
):
    """获取广告总览数据（按推广类型汇总）"""
    query = db.query(
        func.sum(ProductTrafficDetail.ad_spend).label('total_ad_spend'),
        func.avg(ProductTrafficDetail.ad_roi).label('avg_ad_roi'),
        func.sum(ProductTrafficDetail.ad_traffic).label('total_ad_traffic'),
        func.avg(ProductTrafficDetail.ctr).label('avg_ctr'),
        func.avg(ProductTrafficDetail.cpc).label('avg_cpc'),
        func.avg(ProductTrafficDetail.cpm).label('avg_cpm'),
        func.sum(ProductTrafficDetail.impressions).label('total_impressions'),
        func.sum(ProductTrafficDetail.clicks).label('total_clicks'),
        func.sum(ProductTrafficDetail.keyword_ad_spend).label('keyword_spend'),
        func.avg(ProductTrafficDetail.keyword_ad_roi).label('keyword_roi'),
        func.sum(ProductTrafficDetail.keyword_ad_visitors).label('keyword_visitors'),
        func.sum(ProductTrafficDetail.audience_ad_spend).label('audience_spend'),
        func.avg(ProductTrafficDetail.audience_ad_roi).label('audience_roi'),
        func.sum(ProductTrafficDetail.audience_ad_visitors).label('audience_visitors'),
        func.sum(ProductTrafficDetail.scene_ad_spend).label('scene_spend'),
        func.avg(ProductTrafficDetail.scene_ad_roi).label('scene_roi'),
        func.sum(ProductTrafficDetail.scene_ad_visitors).label('scene_visitors'),
        func.sum(ProductTrafficDetail.full_site_ad_spend).label('full_site_spend'),
        func.avg(ProductTrafficDetail.full_site_ad_roi).label('full_site_roi'),
        func.sum(ProductTrafficDetail.full_site_ad_visitors).label('full_site_visitors'),
    ).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
        ProductTrafficDetail.product_id == product_id if product_id else True,
    ).first()
    
    total_spend = query.total_ad_spend or 0
    breakdown = [
        {"type": "关键词推广", "spend": round(query.keyword_spend or 0, 2), "roi": round(query.keyword_roi or 0, 2), "visitors": query.keyword_visitors or 0},
        {"type": "人群推广", "spend": round(query.audience_spend or 0, 2), "roi": round(query.audience_roi or 0, 2), "visitors": query.audience_visitors or 0},
        {"type": "场景推广", "spend": round(query.scene_spend or 0, 2), "roi": round(query.scene_roi or 0, 2), "visitors": query.scene_visitors or 0},
        {"type": "全站推广", "spend": round(query.full_site_spend or 0, 2), "roi": round(query.full_site_roi or 0, 2), "visitors": query.full_site_visitors or 0},
    ]
    
    for b in breakdown:
        b["spend_pct"] = round((b["spend"] / total_spend * 100), 1) if total_spend > 0 else 0
    
    return ResponseModel(data={
        "overview": {
            "total_spend": round(total_spend, 2),
            "avg_roi": round(query.avg_ad_roi or 0, 2),
            "total_traffic": query.total_ad_traffic or 0,
            "avg_ctr": round((query.avg_ctr or 0) * 100, 2),
            "avg_cpc": round(query.avg_cpc or 0, 2),
            "avg_cpm": round(query.avg_cpm or 0, 2),
            "total_impressions": query.total_impressions or 0,
            "total_clicks": query.total_clicks or 0,
        },
        "breakdown": breakdown,
        "period": f"{start_date or '全部'} ~ {end_date or '全部'}",
    })


@router.get("/ad/trend", response_model=ResponseModel)
def get_ad_trend(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    db: Session = Depends(get_db)
):
    """获取广告趋势数据"""
    query = db.query(
        ProductTrafficDetail.date,
        func.sum(ProductTrafficDetail.ad_spend).label('ad_spend'),
        func.avg(ProductTrafficDetail.ad_roi).label('ad_roi'),
        func.sum(ProductTrafficDetail.keyword_ad_spend).label('keyword_spend'),
        func.sum(ProductTrafficDetail.audience_ad_spend).label('audience_spend'),
        func.sum(ProductTrafficDetail.scene_ad_spend).label('scene_spend'),
        func.sum(ProductTrafficDetail.full_site_ad_spend).label('full_site_spend'),
    ).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
        ProductTrafficDetail.product_id == product_id if product_id else True,
    ).group_by(ProductTrafficDetail.date).order_by(ProductTrafficDetail.date).all()
    
    result = []
    for t in query:
        result.append({
            "date": t.date,
            "ad_spend": round(t.ad_spend or 0, 2),
            "ad_roi": round(t.ad_roi or 0, 2),
            "keyword_spend": round(t.keyword_spend or 0, 2),
            "audience_spend": round(t.audience_spend or 0, 2),
            "scene_spend": round(t.scene_spend or 0, 2),
            "full_site_spend": round(t.full_site_spend or 0, 2),
        })
    
    return ResponseModel(data={"trends": result})
