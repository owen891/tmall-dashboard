from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from app.core.database import get_db
from app.models import PaidDetail, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/ads", tags=["广告分析"])


@router.get("/summary", response_model=ResponseModel)
def get_ad_summary(
    product_id: Optional[str] = None,
    dimension: str = Query("keyword", description="广告类型: keyword/crowd/smart/all"),
    db: Session = Depends(get_db)
):
    """获取广告汇总数据"""
    
    if dimension == "all":
        query = db.query(PaidDetail)
    else:
        query = db.query(PaidDetail).filter(PaidDetail.product_id.like(f"%{dimension}%"))
    
    if product_id:
        query = query.filter(PaidDetail.product_id == product_id)
    
    ads = query.all()
    
    if not ads:
        return ResponseModel(data={"summary": {}, "top_keywords": []})
    
    total_impressions = sum(a.impressions or 0 for a in ads)
    total_clicks = sum(a.clicks or 0 for a in ads)
    total_cost = sum(a.cost or 0 for a in ads)
    total_gmv = sum(a.total_gmv or 0 for a in ads)
    total_orders = sum(a.total_orders or 0 for a in ads)
    total_direct = sum(a.direct_gmv or 0 for a in ads)
    total_indirect = sum(a.indirect_gmv or 0 for a in ads)
    total_cart_adds = sum(a.cart_adds or 0 for a in ads)
    total_favs = sum(a.favs or 0 for a in ads)
    total_new_buyers = sum(a.new_buyers or 0 for a in ads)
    
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
    cpm = (total_cost / total_impressions * 1000) if total_impressions > 0 else 0
    overall_roi = (total_gmv / total_cost) if total_cost > 0 else 0
    cart_rate = (total_cart_adds / total_clicks * 100) if total_clicks > 0 else 0
    conv_rate = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
    direct_ratio = (total_direct / total_gmv * 100) if total_gmv > 0 else 0
    
    summary = {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "cost": round(total_cost, 2),
        "gmv": round(total_gmv, 2),
        "orders": total_orders,
        "direct_gmv": round(total_direct, 2),
        "indirect_gmv": round(total_indirect, 2),
        "roi": round(overall_roi, 2),
        "ctr": round(ctr, 2),
        "cpc": round(cpc, 2),
        "cpm": round(cpm, 2),
        "conv_rate": round(conv_rate, 2),
        "cart_rate": round(cart_rate, 2),
        "cart_adds": total_cart_adds,
        "favs": total_favs,
        "new_buyers": total_new_buyers,
        "direct_ratio": round(direct_ratio, 2),
        "ad_count": len(ads)
    }
    
    return ResponseModel(data={"summary": summary})


@router.get("/products", response_model=ResponseModel)
def get_products_ad_performance(
    limit: int = Query(20, description="返回数量"),
    sort_by: str = Query("roi", description="排序字段: roi/gmv/cost/ctr"),
    db: Session = Depends(get_db)
):
    """获取各商品广告效果排名"""
    
    if sort_by == "gmv":
        order_col = func.sum(PaidDetail.total_gmv).desc()
    elif sort_by == "cost":
        order_col = func.sum(PaidDetail.cost).desc()
    elif sort_by == "ctr":
        order_col = func.avg(PaidDetail.ctr).desc()
    else:
        order_by = sort_by
        order_col = func.avg(PaidDetail.roi).desc()
    
    query = db.query(
        PaidDetail.product_id,
        func.sum(PaidDetail.impressions).label('impressions'),
        func.sum(PaidDetail.clicks).label('clicks'),
        func.sum(PaidDetail.cost).label('cost'),
        func.sum(PaidDetail.total_gmv).label('gmv'),
        func.sum(PaidDetail.total_orders).label('orders'),
        func.avg(PaidDetail.ctr).label('ctr'),
        func.avg(PaidDetail.roi).label('roi')
    ).group_by(PaidDetail.product_id)
    
    if sort_by == "gmv":
        products = query.order_by(order_col).limit(limit).all()
    elif sort_by == "cost":
        products = query.order_by(order_col).limit(limit).all()
    elif sort_by == "ctr":
        products = query.order_by(order_col).limit(limit).all()
    else:
        products = query.order_by(order_col).limit(limit).all()
    
    result = []
    for p in products:
        cost = float(p.cost or 0)
        gmv = float(p.gmv or 0)
        impressions = int(p.impressions or 0)
        clicks = int(p.clicks or 0)
        
        product = db.query(Product).filter(Product.product_id == p.product_id).first()
        
        result.append({
            "product_id": p.product_id,
            "title": product.title if product else None,
            "tier": product.tier if product else None,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 2),
            "gmv": round(gmv, 2),
            "orders": int(p.orders or 0),
            "ctr": round(float(p.ctr or 0), 2),
            "roi": round(gmv / cost, 2) if cost > 0 else 0,
            "cpc": round(cost / clicks, 2) if clicks > 0 else 0,
            "cpm": round(cost / impressions * 1000, 2) if impressions > 0 else 0
        })
    
    return ResponseModel(data={
        "products": result,
        "count": len(result)
    })


@router.get("/{product_id}", response_model=ResponseModel)
def get_product_ad_detail(
    product_id: str,
    db: Session = Depends(get_db)
):
    """获取单个商品的广告详情"""
    
    ads = db.query(PaidDetail).filter(
        PaidDetail.product_id == product_id
    ).order_by(desc(PaidDetail.date_range)).all()
    
    if not ads:
        return ResponseModel(data={"ads": [], "summary": {}})
    
    total_impressions = sum(a.impressions or 0 for a in ads)
    total_clicks = sum(a.clicks or 0 for a in ads)
    total_cost = sum(a.cost or 0 for a in ads)
    total_gmv = sum(a.total_gmv or 0 for a in ads)
    
    ads_list = []
    for a in ads:
        ctr = (a.clicks / a.impressions * 100) if a.impressions > 0 else 0
        cpc = (a.cost / a.clicks) if a.clicks > 0 else 0
        roi = (a.total_gmv / a.cost) if a.cost > 0 else 0
        
        ads_list.append({
            "id": a.id,
            "date_range": a.date_range,
            "impressions": a.impressions,
            "clicks": a.clicks,
            "cost": round(a.cost, 2),
            "ctr": round(ctr, 2),
            "cpc": round(cpc, 2),
            "total_gmv": round(a.total_gmv, 2),
            "direct_gmv": round(a.direct_gmv, 2),
            "indirect_gmv": round(a.indirect_gmv, 2),
            "roi": round(roi, 2),
            "cart_adds": a.cart_adds,
            "favs": a.favs,
            "new_buyers": a.new_buyers,
            "orders": a.total_orders
        })
    
    summary = {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "cost": round(total_cost, 2),
        "gmv": round(total_gmv, 2),
        "roi": round(total_gmv / total_cost, 2) if total_cost > 0 else 0,
        "ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
        "cpc": round(total_cost / total_clicks, 2) if total_clicks > 0 else 0
    }
    
    return ResponseModel(data={
        "product_id": product_id,
        "ads": ads_list,
        "summary": summary,
        "count": len(ads_list)
    })


@router.get("/comparison", response_model=ResponseModel)
def compare_ad_channels(
    product_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """对比不同广告渠道效果"""
    
    query = db.query(PaidDetail)
    if product_id:
        query = query.filter(PaidDetail.product_id == product_id)
    
    ads = query.all()
    
    if not ads:
        return ResponseModel(data={"channels": []})
    
    channels = {}
    for a in ads:
        channel = "other"
        if "keyword" in a.product_id.lower():
            channel = "关键词"
        elif "crowd" in a.product_id.lower():
            channel = "人群"
        elif "smart" in a.product_id.lower():
            channel = "智能推广"
        elif "site" in a.product_id.lower():
            channel = "站外推广"
        
        if channel not in channels:
            channels[channel] = {
                "name": channel,
                "impressions": 0,
                "clicks": 0,
                "cost": 0,
                "gmv": 0,
                "orders": 0
            }
        
        channels[channel]["impressions"] += a.impressions or 0
        channels[channel]["clicks"] += a.clicks or 0
        channels[channel]["cost"] += a.cost or 0
        channels[channel]["gmv"] += a.total_gmv or 0
        channels[channel]["orders"] += a.total_orders or 0
    
    result = []
    for name, data in channels.items():
        cost = data["cost"]
        gmv = data["gmv"]
        impressions = data["impressions"]
        clicks = data["clicks"]
        
        result.append({
            "name": data["name"],
            "impressions": data["impressions"],
            "clicks": data["clicks"],
            "cost": round(cost, 2),
            "gmv": round(gmv, 2),
            "orders": data["orders"],
            "roi": round(gmv / cost, 2) if cost > 0 else 0,
            "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            "cpc": round(cost / clicks, 2) if clicks > 0 else 0
        })
    
    result.sort(key=lambda x: x["gmv"], reverse=True)
    
    return ResponseModel(data={"channels": result})
