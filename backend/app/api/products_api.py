from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.core.database import get_db
from app.models.dashboard_models import (
    ProductRanking, ProductProfit, ReviewAnalysis
)

router = APIRouter(prefix="/api/products", tags=["商品矩阵"])


@router.get("/ranking")
async def get_product_ranking(
    tier: Optional[str] = Query(None, description="分层"),
    product_type: Optional[str] = Query(None, description="类型"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """商品排行(A款跑量)"""
    query = db.query(ProductRanking)
    
    if tier:
        query = query.filter(ProductRanking.tier == tier)
    if product_type:
        query = query.filter(ProductRanking.product_type == product_type)
    
    products = query.order_by(desc(ProductRanking.sales_30d)).limit(limit).all()
    
    return {
        "items": [
            {
                "product_id": p.product_id,
                "title": p.title,
                "sales_30d": p.sales_30d,
                "rank": idx + 1,
                "prev_rank": p.prev_rank,
                "rank_change": p.rank_change,
                "ipv": p.ipv,
                "ctr": p.ctr,
                "cvr": p.cvr,
                "search_weight": p.search_weight,
                "product_type": p.product_type,
                "tier": p.tier
            }
            for idx, p in enumerate(products)
        ],
        "total": len(products)
    }


@router.get("/profit")
async def get_product_profit(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """商品利润排行(B款利润)"""
    products = db.query(ProductProfit).order_by(
        desc(ProductProfit.net_profit)
    ).limit(limit).all()
    
    return {
        "items": [
            {
                "product_id": p.product_id,
                "title": p.title,
                "gmv": p.gmv,
                "purchase_cost": p.purchase_cost,
                "freight": p.freight,
                "ad_cost": p.ad_cost,
                "net_profit": p.net_profit,
                "ad_ratio": p.ad_ratio,
                "roi": p.roi,
                "gross_margin": p.gross_margin,
                "break_even_roi": p.break_even_roi,
                "suggestion": p.suggestion
            }
            for p in products
        ],
        "total": len(products)
    }


@router.get("/reviews")
async def get_review_analysis(
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("negative_rate", description="排序字段"),
    db: Session = Depends(get_db)
):
    """评价分析"""
    query = db.query(ReviewAnalysis)
    
    if sort_by == "negative_rate":
        query = query.order_by(desc(ReviewAnalysis.negative_rate))
    else:
        query = query.order_by(desc(ReviewAnalysis.total_reviews))
    
    reviews = query.limit(limit).all()
    
    return {
        "items": [
            {
                "product_id": r.product_id,
                "title": r.title,
                "total_reviews": r.total_reviews,
                "star1": r.star1,
                "star2": r.star2,
                "star3": r.star3,
                "star4": r.star4,
                "star5": r.star5,
                "negative_rate": r.negative_rate,
                "positive_rate": r.positive_rate,
                "defect_words": r.defect_words,
                "positive_words": r.positive_words
            }
            for r in reviews
        ],
        "total": len(reviews)
    }


@router.get("/matrix")
async def get_product_matrix(
    db: Session = Depends(get_db)
):
    """商品矩阵(四象限)"""
    products = db.query(ProductRanking).all()
    
    matrix = {
        "star": [],
        "cash_cow": [],
        "question": [],
        "dog": []
    }
    
    for p in products:
        data = {
            "product_id": p.product_id,
            "title": p.title,
            "sales_30d": p.sales_30d,
            "search_weight": p.search_weight,
            "ctr": p.ctr,
            "cvr": p.cvr,
            "tier": p.tier
        }
        
        if p.sales_rank <= 20 and p.search_weight >= 0.7:
            matrix["star"].append(data)
        elif p.sales_rank <= 50 and p.search_weight >= 0.5:
            matrix["cash_cow"].append(data)
        elif p.search_weight < 0.3:
            matrix["dog"].append(data)
        else:
            matrix["question"].append(data)
    
    return {
        "items": matrix,
        "total": len(products)
    }


@router.get("/summary")
async def get_product_summary(
    db: Session = Depends(get_db)
):
    """商品汇总"""
    total_products = db.query(func.count(ProductRanking.id)).scalar() or 0
    
    tier_stats = db.query(
        ProductRanking.tier,
        func.count(ProductRanking.id).label("count"),
        func.sum(ProductRanking.sales_30d).label("total_sales")
    ).group_by(ProductRanking.tier).all()
    
    avg_profit = db.query(func.avg(ProductProfit.net_profit)).scalar() or 0
    total_gmv = db.query(func.sum(ProductProfit.gmv)).scalar() or 0
    
    return {
        "total_products": total_products,
        "tier_stats": [
            {
                "tier": t.tier,
                "count": t.count,
                "total_sales": t.total_sales or 0
            }
            for t in tier_stats
        ],
        "avg_profit": avg_profit,
        "total_gmv": total_gmv
    }
