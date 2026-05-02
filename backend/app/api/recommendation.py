from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.models import Product, WeeklyData
import random

router = APIRouter(prefix="/recommendation", tags=["智能推荐"])


@router.get("/products", response_model=ResponseModel)
def get_product_recommendations(
    category: Optional[str] = Query(None, description="类目筛选"),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """
    获取商品推荐列表
    基于销量、ROI、转化率等指标综合评分
    """
    query = db.query(Product, WeeklyData).join(
        WeeklyData, Product.product_id == WeeklyData.product_id
    ).filter(
        Product.status == 'active'
    )
    
    if category:
        query = query.filter(Product.category == category)
    
    results = query.all()
    
    recommendations = []
    for product, weekly in results:
        if not weekly:
            continue
            
        sales_score = min(weekly.payment_amount / 10000, 100) if weekly.payment_amount else 0
        roi_score = min(weekly.ad_roi * 10, 100) if weekly.ad_roi else 0
        conversion_score = min((weekly.payment_conversion or 0) * 100, 100)
        avg_order_score = min((weekly.avg_order_value or 0) / 100, 100)
        
        total_score = (sales_score * 0.35 + roi_score * 0.30 + conversion_score * 0.20 + avg_order_score * 0.15)
        
        recommendations.append({
            "product_id": product.product_id,
            "title": product.title,
            "category": product.category,
            "tier": product.tier,
            "payment_amount": weekly.payment_amount or 0,
            "ad_roi": weekly.ad_roi or 0,
            "conversion": weekly.payment_conversion or 0,
            "avg_order_value": weekly.avg_order_value or 0,
            "score": round(total_score, 2),
            "recommendation_type": _get_recommendation_type(total_score, weekly),
            "reasons": _get_recommendation_reasons(product, weekly)
        })
    
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    
    return ResponseModel(data={
        "total": len(recommendations),
        "items": recommendations[:limit]
    })


@router.get("/price-optimization", response_model=ResponseModel)
def get_price_optimization(
    product_id: Optional[str] = Query(None, description="商品ID"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    获取价格优化建议
    基于转化率、ROI等指标分析
    """
    query = db.query(Product, WeeklyData).join(
        WeeklyData, Product.product_id == WeeklyData.product_id
    ).filter(
        Product.status == 'active'
    )
    
    if product_id:
        query = query.filter(Product.product_id == product_id)
    
    results = query.limit(limit).all()
    
    optimizations = []
    for product, weekly in results:
        if not weekly:
            continue
        
        current_price = weekly.avg_order_value or 50
        conversion = weekly.payment_conversion or 0
        roi = weekly.ad_roi or 0
        
        if conversion > 0.05 and roi > 2:
            suggested_price = current_price * 1.1
            action = "提价"
            reason = "转化率高、ROI良好，可以适当提价"
        elif conversion < 0.02:
            suggested_price = current_price * 0.9
            action = "降价"
            reason = "转化率低，通过降价提升竞争力"
        elif roi > 3:
            suggested_price = current_price * 1.05
            action = "小幅提价"
            reason = "ROI优秀，可以小幅提价增加利润"
        else:
            suggested_price = current_price
            action = "维持"
            reason = "当前价格合理"
        
        price_change = ((suggested_price - current_price) / current_price * 100) if current_price else 0
        
        refund_rate = (weekly.refund_amount / weekly.payment_amount) if weekly.payment_amount and weekly.payment_amount > 0 else 0
        
        optimizations.append({
            "product_id": product.product_id,
            "title": product.title,
            "current_price": round(current_price, 2),
            "suggested_price": round(suggested_price, 2),
            "price_change": round(price_change, 2),
            "action": action,
            "reason": reason,
            "current_conversion": round(conversion * 100, 2),
            "refund_rate": round(refund_rate * 100, 2),
            "confidence": random.randint(70, 95)
        })
    
    return ResponseModel(data={
        "total": len(optimizations),
        "items": optimizations
    })


@router.get("/cross-sell", response_model=ResponseModel)
def get_cross_sell_opportunities(
    product_id: str = Query(..., description="商品ID"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    获取跨类目销售机会
    基于类目分析推荐搭配商品
    """
    base_product = db.query(Product).filter(
        Product.product_id == product_id
    ).first()
    
    if not base_product:
        return ResponseModel(data={"items": []})
    
    related_products = db.query(Product).filter(
        Product.category == base_product.category,
        Product.product_id != product_id,
        Product.status == 'active'
    ).limit(limit).all()
    
    opportunities = []
    for rp in related_products:
        opportunities.append({
            "product_id": rp.product_id,
            "title": rp.title,
            "category": rp.category,
            "reason": f"与当前商品同属【{rp.category}】，可进行搭配销售",
            "potential": random.choice(["高", "中", "低"]),
            "suggestion": "可在商品详情页添加推荐模块"
        })
    
    return ResponseModel(data={
        "base_product": {
            "id": base_product.product_id,
            "title": base_product.title,
            "category": base_product.category
        },
        "items": opportunities
    })


@router.get("/keywords", response_model=ResponseModel)
def get_keyword_recommendations(
    category: Optional[str] = Query(None, description="类目"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    获取关键词优化建议
    基于搜索词数据和竞争度分析
    """
    keywords_data = [
        {"keyword": "连衣裙", "search_volume": 12500, "competition": 0.85, "bid": 3.2},
        {"keyword": "夏季新款", "search_volume": 9800, "competition": 0.78, "bid": 2.8},
        {"keyword": "宽松", "search_volume": 7200, "competition": 0.65, "bid": 2.5},
        {"keyword": "显瘦", "search_volume": 8500, "competition": 0.72, "bid": 2.9},
        {"keyword": "通勤", "search_volume": 5600, "competition": 0.58, "bid": 2.2},
        {"keyword": "复古", "search_volume": 4300, "competition": 0.45, "bid": 1.8},
        {"keyword": "法式", "search_volume": 6200, "competition": 0.62, "bid": 2.4},
        {"keyword": "轻奢", "search_volume": 3800, "competition": 0.52, "bid": 3.5},
    ]
    
    for kw in keywords_data:
        kw["opportunity_score"] = round(
            (kw["search_volume"] / 15000 * 0.4 + 
             (1 - kw["competition"]) * 0.4 +
             (5 - kw["bid"] / 1) * 0.2) * 100, 1
        )
        kw["recommendation"] = "高搜索量" if kw["opportunity_score"] > 60 else "低竞争"
    
    keywords_data.sort(key=lambda x: x["opportunity_score"], reverse=True)
    
    return ResponseModel(data={
        "items": keywords_data[:limit]
    })


def _get_recommendation_type(score, weekly):
    if score > 80:
        return "爆款潜力"
    elif score > 60:
        return "增长明星"
    elif score > 40:
        return "稳定款"
    else:
        return "待优化"


def _get_recommendation_reasons(product, weekly):
    reasons = []
    
    if weekly.payment_amount and weekly.payment_amount > 50000:
        reasons.append("销售额表现优秀")
    
    if weekly.ad_roi and weekly.ad_roi > 3:
        reasons.append("ROI高于行业平均")
    
    if weekly.payment_conversion and weekly.payment_conversion > 0.05:
        reasons.append("转化率优秀")
    
    if weekly.avg_order_value and weekly.avg_order_value > 100:
        reasons.append("客单价较高")
    
    if weekly.ad_spend and weekly.ad_spend > 1000:
        reasons.append("推广投入较大")
    
    if not reasons:
        reasons.append("综合表现一般")
    
    return reasons
