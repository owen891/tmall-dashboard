from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
from typing import Optional, List
from app.core.database import get_db
from app.models.command_tower import (
    WxtCampaign, WxtDailyMetrics, DmpCrowd, DmpCampaignLink, CrowdAssetStats
)
from app.schemas.common import ResponseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/crowd-asset", tags=["人群资产归因"])


@router.get("/campaigns", response_model=ResponseModel)
def get_campaigns(
    status: Optional[str] = None,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取万相台投放计划列表"""
    query = db.query(WxtCampaign)
    if status:
        query = query.filter(WxtCampaign.status == status)
    
    total = query.count()
    campaigns = query.order_by(desc(WxtCampaign.created_at)).offset(offset).limit(limit).all()
    
    # 补充统计数据
    result = []
    for campaign in campaigns:
        latest_metrics = db.query(WxtDailyMetrics).filter(
            WxtDailyMetrics.campaign_id == campaign.id
        ).order_by(desc(WxtDailyMetrics.date)).first()
        
        result.append({
            "id": campaign.id,
            "campaign_name": campaign.campaign_name,
            "campaign_type": campaign.campaign_type,
            "status": campaign.status,
            "budget": campaign.budget,
            "actual_spend": campaign.actual_spend,
            "manager": campaign.manager,
            "latest_metrics": {
                "gmv": latest_metrics.total_gmv if latest_metrics else 0,
                "roi": latest_metrics.roi if latest_metrics else 0,
                "cost": latest_metrics.cost if latest_metrics else 0
            } if latest_metrics else None,
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None
        })
    
    return ResponseModel(data={"campaigns": result, "total": total})


@router.get("/campaigns/{campaign_id}", response_model=ResponseModel)
def get_campaign_detail(campaign_id: int, db: Session = Depends(get_db)):
    """获取投放计划详情"""
    campaign = db.query(WxtCampaign).filter(WxtCampaign.id == campaign_id).first()
    if not campaign:
        return ResponseModel(code=404, message="计划不存在")
    
    # 获取关联人群
    crowds = db.query(DmpCrowd).join(
        DmpCampaignLink, DmpCampaignLink.crowd_id == DmpCrowd.id
    ).filter(DmpCampaignLink.campaign_id == campaign_id).all()
    
    # 获取最近30天数据
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    metrics_list = db.query(WxtDailyMetrics).filter(
        and_(
            WxtDailyMetrics.campaign_id == campaign_id,
            WxtDailyMetrics.date >= thirty_days_ago
        )
    ).order_by(WxtDailyMetrics.date).all()
    
    return ResponseModel(data={
        "campaign": {
            "id": campaign.id,
            "campaign_name": campaign.campaign_name,
            "campaign_type": campaign.campaign_type,
            "status": campaign.status,
            "start_date": campaign.start_date,
            "end_date": campaign.end_date,
            "budget": campaign.budget,
            "actual_spend": campaign.actual_spend,
            "target_roi": campaign.target_roi,
            "target_cpa": campaign.target_cpa,
            "manager": campaign.manager
        },
        "crowds": [{
            "id": c.id,
            "crowd_name": c.crowd_name,
            "tier": c.tier,
            "scale": c.scale,
            "bid_ratio": c.actual_bid_ratio
        } for c in crowds],
        "metrics": [{
            "date": m.date,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost": m.cost,
            "ctr": m.ctr,
            "total_gmv": m.total_gmv,
            "roi": m.roi,
            "new_customers": m.new_customers,
            "cart_adds": m.cart_adds
        } for m in metrics_list]
    })


@router.get("/crowds", response_model=ResponseModel)
def get_crowds(
    tier: Optional[str] = None,
    is_active: Optional[bool] = True,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取达摩盘人群包列表"""
    query = db.query(DmpCrowd).filter(DmpCrowd.is_active == is_active)
    if tier:
        query = query.filter(DmpCrowd.tier == tier)
    
    total = query.count()
    crowds = query.order_by(desc(DmpCrowd.created_at)).offset(offset).limit(limit).all()
    
    return ResponseModel(data={
        "crowds": [{
            "id": c.id,
            "crowd_name": c.crowd_name,
            "crowd_code": c.crowd_code,
            "tier": c.tier,
            "scale": c.scale,
            "suggested_bid_ratio": c.suggested_bid_ratio,
            "actual_bid_ratio": c.actual_bid_ratio,
            "manager": c.manager
        } for c in crowds],
        "total": total
    })


@router.get("/dashboard", response_model=ResponseModel)
def get_crowd_asset_dashboard(db: Session = Depends(get_db)):
    """人群资产总览"""
    # 总花费与GMV
    total_cost = db.query(func.sum(WxtDailyMetrics.cost)).scalar() or 0
    total_gmv = db.query(func.sum(WxtDailyMetrics.total_gmv)).scalar() or 0
    
    # 人群规模
    total_scale = db.query(func.sum(DmpCrowd.scale)).scalar() or 0
    
    # AIPL新增统计
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_stats = db.query(CrowdAssetStats).filter(
        CrowdAssetStats.created_at >= seven_days_ago
    ).all()
    
    total_a_increase = sum(s.awareness_increase for s in recent_stats)
    total_i_increase = sum(s.interest_increase for s in recent_stats)
    total_p_increase = sum(s.purchase_increase for s in recent_stats)
    total_l_increase = sum(s.loyalty_increase for s in recent_stats)
    
    # TOP人群（按ROI排序）
    top_crowds = []
    stats_list = db.query(CrowdAssetStats).filter(CrowdAssetStats.period == "30d").all()
    for stat in stats_list:
        crowd = db.query(DmpCrowd).filter(DmpCrowd.id == stat.crowd_id).first()
        if crowd:
            top_crowds.append({
                "crowd_name": crowd.crowd_name,
                "tier": crowd.tier,
                "asset_roi": stat.asset_roi,
                "water_score": stat.water_capacity_score,
                "harvest_score": stat.harvest_capacity_score
            })
    top_crowds = sorted(top_crowds, key=lambda x: x["asset_roi"], reverse=True)[:10]
    
    return ResponseModel(data={
        "summary": {
            "total_cost": total_cost,
            "total_gmv": total_gmv,
            "total_roi": total_gmv / total_cost if total_cost > 0 else 0,
            "total_crowd_scale": total_scale
        },
        "aipl_increase": {
            "awareness": total_a_increase,
            "interest": total_i_increase,
            "purchase": total_p_increase,
            "loyalty": total_l_increase
        },
        "top_crowds": top_crowds
    })


@router.get("/efficiency-matrix", response_model=ResponseModel)
def get_efficiency_matrix(db: Session = Depends(get_db)):
    """人群×出价效率矩阵"""
    # 获取所有活跃人群
    crowds = db.query(DmpCrowd).filter(DmpCrowd.is_active == True).all()
    
    matrix_data = []
    for crowd in crowds:
        # 获取最近30天统计
        recent_stats = db.query(CrowdAssetStats).filter(
            and_(
                CrowdAssetStats.crowd_id == crowd.id,
                CrowdAssetStats.period == "30d"
            )
        ).order_by(desc(CrowdAssetStats.created_at)).first()
        
        matrix_data.append({
            "crowd_name": crowd.crowd_name,
            "tier": crowd.tier,
            "bid_ratio": crowd.actual_bid_ratio,
            "scale": crowd.scale,
            "asset_roi": recent_stats.asset_roi if recent_stats else 0,
            "water_score": recent_stats.water_capacity_score if recent_stats else 0,
            "harvest_score": recent_stats.harvest_capacity_score if recent_stats else 0,
            "recommended_adjustment": "raise_bid" if (
                recent_stats and recent_stats.harvest_capacity_score > 70
            ) else "lower_bid" if (
                recent_stats and recent_stats.harvest_capacity_score < 30
            ) else "maintain"
        })
    
    return ResponseModel(data={"matrix": matrix_data})


@router.post("/crowds/{crowd_id}/update-bid", response_model=ResponseModel)
def update_crowd_bid(
    crowd_id: int,
    bid_ratio: float,
    db: Session = Depends(get_db)
):
    """更新人群出价系数"""
    crowd = db.query(DmpCrowd).filter(DmpCrowd.id == crowd_id).first()
    if not crowd:
        return ResponseModel(code=404, message="人群包不存在")
    
    crowd.actual_bid_ratio = bid_ratio
    crowd.updated_at = datetime.now()
    db.commit()
    
    return ResponseModel(data={"message": "出价系数已更新"})

