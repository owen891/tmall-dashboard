from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.core.database import get_db
from app.models.dashboard_models import (
    KeywordMetrics, FunnelMetrics, CompetitorShare
)

router = APIRouter(prefix="/traffic", tags=["流量漏斗"])


@router.get("/keywords")
async def get_keywords(
    date: Optional[str] = Query(None, description="日期"),
    category: Optional[str] = Query(None, description="分类筛选"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """搜索词效能矩阵"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    query = db.query(KeywordMetrics).filter(
        KeywordMetrics.date == date
    )
    
    if category:
        query = query.filter(KeywordMetrics.category == category)
    
    keywords = query.order_by(desc(KeywordMetrics.efficacy)).limit(limit).all()
    
    return {
        "items": [
            {
                "keyword": k.keyword,
                "popularity": k.popularity,
                "impressions": k.impressions,
                "clicks": k.clicks,
                "ctr": k.ctr,
                "cvr": k.cvr,
                "efficacy": k.efficacy,
                "category": k.category,
                "gmv": k.gmv,
                "cost": k.cost,
                "roi": k.roi
            }
            for k in keywords
        ],
        "total": len(keywords),
        "date": date
    }


@router.get("/keywords/stats")
async def get_keywords_stats(
    date: Optional[str] = Query(None, description="日期"),
    db: Session = Depends(get_db)
):
    """搜索词统计"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    total = db.query(func.count(KeywordMetrics.id)).filter(
        KeywordMetrics.date == date
    ).scalar() or 0
    
    blue_ocean = db.query(func.count(KeywordMetrics.id)).filter(
        KeywordMetrics.date == date,
        KeywordMetrics.category == '蓝海词'
    ).scalar() or 0
    
    traffic = db.query(func.count(KeywordMetrics.id)).filter(
        KeywordMetrics.date == date,
        KeywordMetrics.category == '流量词'
    ).scalar() or 0
    
    waste = db.query(func.count(KeywordMetrics.id)).filter(
        KeywordMetrics.date == date,
        KeywordMetrics.category == '废词'
    ).scalar() or 0
    
    return {
        "total": total,
        "blue_ocean": blue_ocean,
        "traffic": traffic,
        "waste": waste,
        "date": date
    }


@router.get("/funnel")
async def get_funnel(
    date: Optional[str] = Query(None, description="日期"),
    db: Session = Depends(get_db)
):
    """转化漏斗"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    funnel = db.query(FunnelMetrics).filter(
        FunnelMetrics.date == date
    ).first()
    
    if not funnel:
        return {
            "impression": 0,
            "click": 0,
            "cart": 0,
            "pay": 0,
            "bounce": 0,
            "ctr": 0,
            "cart_rate": 0,
            "cvr": 0,
            "bounce_rate": 0,
            "date": date
        }
    
    return {
        "impression": funnel.impression_uv,
        "click": funnel.click_uv,
        "cart": funnel.cart_uv,
        "pay": funnel.pay_buyers,
        "bounce": funnel.bounce_uv,
        "total_uv": funnel.total_uv,
        "ctr": funnel.ctr,
        "cart_rate": funnel.cart_rate,
        "cvr": funnel.cvr,
        "bounce_rate": funnel.bounce_rate,
        "date": date
    }


@router.get("/funnel/trend")
async def get_funnel_trend(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """漏斗趋势"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    
    funnels = db.query(FunnelMetrics).filter(
        FunnelMetrics.date >= start_date.strftime("%Y-%m-%d"),
        FunnelMetrics.date <= end_date.strftime("%Y-%m-%d")
    ).order_by(FunnelMetrics.date).all()
    
    return {
        "items": [
            {
                "date": f.date,
                "impression": f.impression_uv,
                "click": f.click_uv,
                "cart": f.cart_uv,
                "pay": f.pay_buyers,
                "ctr": f.ctr,
                "cvr": f.cvr
            }
            for f in funnels
        ]
    }


@router.get("/competitor")
async def get_competitor_share(
    date: Optional[str] = Query(None, description="日期"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """竞品份额"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    competitors = db.query(CompetitorShare).filter(
        CompetitorShare.date == date
    ).order_by(desc(CompetitorShare.share)).limit(limit).all()
    
    return {
        "items": [
            {
                "keyword": c.keyword,
                "our_uv": c.our_uv,
                "comp_uv": c.comp_uv,
                "share": c.share,
                "share_change": c.share_change
            }
            for c in competitors
        ],
        "date": date
    }


@router.post("/keywords/categorize")
async def categorize_keywords(
    date: Optional[str] = Query(None, description="日期"),
    db: Session = Depends(get_db)
):
    """关键词分类"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    keywords = db.query(KeywordMetrics).filter(
        KeywordMetrics.date == date
    ).all()
    
    for k in keywords:
        if k.efficacy >= 1.2:
            k.category = '蓝海词'
        elif k.efficacy >= 0.8:
            k.category = '流量词'
        else:
            k.category = '废词'
    
    db.commit()
    
    return {"success": True, "count": len(keywords)}
