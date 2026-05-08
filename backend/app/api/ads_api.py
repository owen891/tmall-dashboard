from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.core.database import get_db
from app.models.dashboard_models import (
    CampaignMetrics, AIPLStats
)

router = APIRouter(prefix="/ads", tags=["投放效果"])


@router.get("/campaigns")
async def get_campaigns(
    campaign_type: Optional[str] = Query(None, description="类型"),
    status: Optional[str] = Query(None, description="状态"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """推广排行"""
    query = db.query(CampaignMetrics)
    
    if campaign_type:
        query = query.filter(CampaignMetrics.campaign_type == campaign_type)
    if status:
        query = query.filter(CampaignMetrics.status == status)
    
    campaigns = query.order_by(desc(CampaignMetrics.roi)).limit(limit).all()
    
    return {
        "items": [
            {
                "campaign_id": c.campaign_id,
                "campaign_name": c.campaign_name,
                "campaign_type": c.campaign_type,
                "cost": c.cost,
                "impressions": c.impressions,
                "clicks": c.clicks,
                "conversions": c.conversions,
                "campaign_gmv": c.campaign_gmv,
                "roi": c.roi,
                "cpa": c.cpa,
                "cpm": c.cpm,
                "ppc": c.ppc,
                "status": c.status
            }
            for c in campaigns
        ],
        "total": len(campaigns)
    }


@router.get("/aipl")
async def get_aipl(
    date: Optional[str] = Query(None, description="日期"),
    db: Session = Depends(get_db)
):
    """AIPL流转"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    aipl = db.query(AIPLStats).filter(
        AIPLStats.date == date
    ).first()
    
    if not aipl:
        return {
            "a_count": 0,
            "i_count": 0,
            "p_count": 0,
            "l_count": 0,
            "a_to_i": 0,
            "i_to_p": 0,
            "p_to_l": 0,
            "date": date
        }
    
    return {
        "a_count": aipl.a_count,
        "i_count": aipl.i_count,
        "p_count": aipl.p_count,
        "l_count": aipl.l_count,
        "a_to_i": aipl.a_to_i,
        "i_to_p": aipl.i_to_p,
        "p_to_l": aipl.p_to_l,
        "total": aipl.a_count + aipl.i_count + aipl.p_count + aipl.l_count,
        "date": date
    }


@router.get("/aipl/trend")
async def get_aipl_trend(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """AIPL趋势"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    
    stats = db.query(AIPLStats).filter(
        AIPLStats.date >= start_date.strftime("%Y-%m-%d"),
        AIPLStats.date <= end_date.strftime("%Y-%m-%d")
    ).order_by(AIPLStats.date).all()
    
    return {
        "items": [
            {
                "date": s.date,
                "a_count": s.a_count,
                "i_count": s.i_count,
                "p_count": s.p_count,
                "l_count": s.l_count,
                "a_to_i": s.a_to_i,
                "i_to_p": s.i_to_p,
                "p_to_l": s.p_to_l
            }
            for s in stats
        ]
    }


@router.get("/dmp")
async def get_dmp_crowds(
    level: Optional[str] = Query(None, description="层级"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """达摩盘人群"""
    query = db.query(DmpCrowd)
    
    if level:
        query = query.filter(DmpCrowd.level == level)
    
    crowds = query.order_by(desc(DmpCrowd.crowd_size)).limit(limit).all()
    
    return {
        "items": [
            {
                "crowd_id": c.crowd_id,
                "crowd_name": c.crowd_name,
                "crowd_size": c.crowd_size,
                "level": c.level,
                "bid_coefficient": c.bid_coefficient,
                "roi": c.roi,
                "quadrant": c.quadrant
            }
            for c in crowds
        ],
        "total": len(crowds)
    }


@router.get("/summary")
async def get_ads_summary(
    db: Session = Depends(get_db)
):
    """投放汇总"""
    total_cost = db.query(func.sum(CampaignMetrics.cost)).scalar() or 0
    total_gmv = db.query(func.sum(CampaignMetrics.campaign_gmv)).scalar() or 0
    avg_roi = db.query(func.avg(CampaignMetrics.roi)).scalar() or 0
    
    active = db.query(func.count(CampaignMetrics.id)).filter(
        CampaignMetrics.status == 'running'
    ).scalar() or 0
    
    return {
        "total_cost": total_cost,
        "total_gmv": total_gmv,
        "avg_roi": round(avg_roi, 2),
        "active_campaigns": active,
        "overall_roi": round(total_gmv / total_cost, 2) if total_cost > 0 else 0
    }
