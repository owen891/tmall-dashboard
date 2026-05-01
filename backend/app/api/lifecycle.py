from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from app.core.database import get_db
from app.models import WeeklyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/lifecycle", tags=["生命周期分析"])


def determine_lifecycle_stage(product_id: str, db: Session) -> dict:
    """判断商品生命周期阶段"""
    
    weeks = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id
    ).order_by(desc(WeeklyData.week_start)).limit(8).all()
    
    if len(weeks) < 4:
        return {
            "stage": "new",
            "description": "新品期",
            "confidence": 0.5
        }
    
    weeks.reverse()
    
    gmv_trend = []
    for w in weeks:
        if w.payment_amount:
            gmv_trend.append(w.payment_amount)
    
    if len(gmv_trend) < 4:
        return {
            "stage": "new",
            "description": "新品期",
            "confidence": 0.5
        }
    
    recent_4 = gmv_trend[-4:]
    older_4 = gmv_trend[:4] if len(gmv_trend) >= 8 else gmv_trend[:len(gmv_trend)//2]
    
    if not older_4 or not recent_4:
        return {
            "stage": "unknown",
            "description": "数据不足",
            "confidence": 0
        }
    
    recent_avg = sum(recent_4) / len(recent_4)
    older_avg = sum(older_4) / len(older_4)
    
    if older_avg == 0:
        growth_rate = 0
    else:
        growth_rate = (recent_avg - older_avg) / older_avg * 100
    
    recent_weeks = weeks[-4:]
    visitors_trend = [w.ipv for w in recent_weeks if w.ipv]
    
    if len(visitors_trend) >= 2:
        visitor_change = (visitors_trend[-1] - visitors_trend[0]) / visitors_trend[0] * 100 if visitors_trend[0] > 0 else 0
    else:
        visitor_change = 0
    
    if len(gmv_trend) <= 4:
        stage = "growth"
        description = "成长期"
        confidence = 0.7
    elif growth_rate > 20 and visitor_change > 10:
        stage = "growth"
        description = "成长期"
        confidence = 0.85
    elif growth_rate > 5 and growth_rate <= 20:
        stage = "stable"
        description = "稳定期"
        confidence = 0.8
    elif growth_rate >= -5 and growth_rate <= 5:
        stage = "stable"
        description = "稳定期"
        confidence = 0.75
    elif growth_rate >= -20 and growth_rate < -5:
        stage = "decline"
        description = "衰退期预警"
        confidence = 0.8
    else:
        stage = "serious_decline"
        description = "严重衰退"
        confidence = 0.85
    
    return {
        "stage": stage,
        "description": description,
        "confidence": confidence,
        "growth_rate": round(growth_rate, 2),
        "visitor_change": round(visitor_change, 2),
        "recent_avg_gmv": round(recent_avg, 2),
        "older_avg_gmv": round(older_avg, 2)
    }


@router.get("/product/{product_id}", response_model=ResponseModel)
def get_product_lifecycle(product_id: str, db: Session = Depends(get_db)):
    """获取商品生命周期阶段"""
    
    product = db.query(Product).filter(Product.product_id == product_id).first()
    
    lifecycle = determine_lifecycle_stage(product_id, db)
    
    weeks = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id
    ).order_by(desc(WeeklyData.week_start)).limit(8).all()
    
    trend = []
    for w in reversed(weeks):
        trend.append({
            "period": w.week_start.isoformat(),
            "gmv": w.payment_amount,
            "visitors": w.ipv,
            "conversion": w.payment_conversion,
            "roi": w.ad_roi
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "title": product.title if product else None,
        "lifecycle": lifecycle,
        "trend": trend
    })


@router.get("/list", response_model=ResponseModel)
def get_lifecycle_list(
    stage: Optional[str] = Query(None, description="生命周期阶段"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取各商品生命周期列表"""
    
    products = db.query(Product).all()
    
    lifecycle_list = []
    for product in products:
        lifecycle = determine_lifecycle_stage(product.product_id, db)
        lifecycle["product_id"] = product.product_id
        lifecycle["title"] = product.title
        lifecycle["tier"] = product.tier
        
        if stage and lifecycle["stage"] != stage:
            continue
        
        lifecycle_list.append(lifecycle)
    
    lifecycle_list.sort(key=lambda x: x["growth_rate"], reverse=True)
    
    return ResponseModel(data={
        "products": lifecycle_list[:limit],
        "count": len(lifecycle_list),
        "by_stage": {
            "growth": len([l for l in lifecycle_list if l["stage"] == "growth"]),
            "stable": len([l for l in lifecycle_list if l["stage"] == "stable"]),
            "decline": len([l for l in lifecycle_list if l["stage"] == "decline"]),
            "serious_decline": len([l for l in lifecycle_list if l["stage"] == "serious_decline"])
        }
    })


@router.get("/statistics", response_model=ResponseModel)
def get_lifecycle_statistics(db: Session = Depends(get_db)):
    """获取生命周期分布统计"""
    
    products = db.query(Product).all()
    
    stages = {
        "growth": [],
        "stable": [],
        "decline": [],
        "serious_decline": [],
        "new": [],
        "unknown": []
    }
    
    for product in products:
        lifecycle = determine_lifecycle_stage(product.product_id, db)
        stage = lifecycle["stage"]
        
        stages[stage].append({
            "product_id": product.product_id,
            "title": product.title,
            "tier": product.tier,
            "growth_rate": lifecycle["growth_rate"]
        })
    
    total = len(products)
    
    distribution = {
        stage: {
            "count": len(products_list),
            "percentage": round(len(products_list) / total * 100, 1) if total > 0 else 0
        }
        for stage, products_list in stages.items()
    }
    
    avg_growth = {
        "growth": 0,
        "stable": 0,
        "decline": 0
    }
    
    for stage in ["growth", "stable", "decline"]:
        if stages[stage]:
            avg_growth[stage] = round(
                sum(p["growth_rate"] for p in stages[stage]) / len(stages[stage]), 
                2
            )
    
    return ResponseModel(data={
        "total_products": total,
        "distribution": distribution,
        "average_growth": avg_growth,
        "top_growth": stages["growth"][:5] if stages["growth"] else [],
        "serious_decline": stages["serious_decline"][:5] if stages["serious_decline"] else []
    })


@router.get("/recommendations", response_model=ResponseModel)
def get_lifecycle_recommendations(
    product_id: str,
    db: Session = Depends(get_db)
):
    """获取生命周期优化建议"""
    
    lifecycle = determine_lifecycle_stage(product_id, db)
    
    recommendations = []
    
    if lifecycle["stage"] == "new":
        recommendations = [
            {"type": "info", "message": "新品期：重点优化主图和详情页，提升点击率和转化率"},
            {"type": "info", "message": "适当投入广告测款，关注收藏加购数据"},
            {"type": "info", "message": "收集用户评价，了解用户需求和痛点"}
        ]
    elif lifecycle["stage"] == "growth":
        recommendations = [
            {"type": "success", "message": "成长期：加大广告投入，扩大流量来源"},
            {"type": "success", "message": "关注转化率优化，提升UV价值"},
            {"type": "info", "message": "做好库存管理，避免断货影响销售"},
            {"type": "info", "message": "考虑老客户复购营销"}
        ]
    elif lifecycle["stage"] == "stable":
        recommendations = [
            {"type": "warning", "message": "稳定期：维持现有推广力度，控制广告成本"},
            {"type": "info", "message": "优化评价管理，保持好评率"},
            {"type": "info", "message": "关注竞品动态，适时调整价格策略"},
            {"type": "info", "message": "开发关联产品，寻找新增长点"}
        ]
    elif lifecycle["stage"] == "decline":
        recommendations = [
            {"type": "danger", "message": "衰退预警：分析衰退原因（季节性/竞品/产品问题）"},
            {"type": "warning", "message": "减少广告投入，避免无效消耗"},
            {"type": "info", "message": "考虑清仓促销，回笼资金"},
            {"type": "info", "message": "开发升级款或替代产品"}
        ]
    else:
        recommendations = [
            {"type": "danger", "message": "严重衰退：立即停止广告投入"},
            {"type": "danger", "message": "大幅降价清仓，清理库存"},
            {"type": "info", "message": "总结失败原因，为新品开发积累经验"}
        ]
    
    return ResponseModel(data={
        "product_id": product_id,
        "lifecycle": lifecycle,
        "recommendations": recommendations
    })
