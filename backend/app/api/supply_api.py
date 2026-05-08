from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.core.database import get_db
from app.models.dashboard_models import (
    InventoryStatus, SlowMoving
)

router = APIRouter(prefix="/supply", tags=["供应链"])


@router.get("/inventory")
async def get_inventory_alerts(
    level: Optional[str] = Query(None, description="预警级别"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """库存预警"""
    query = db.query(InventoryStatus)
    
    if level:
        query = query.filter(InventoryStatus.alert_level == level)
    else:
        query = query.filter(InventoryStatus.alert_level != 'green')
    
    items = query.order_by(InventoryStatus.days_remaining).limit(limit).all()
    
    return {
        "items": [
            {
                "sku_id": i.sku_id,
                "product_id": i.product_id,
                "sku_name": i.sku_name,
                "current_stock": i.current_stock,
                "avg_daily_sales_7d": i.avg_daily_sales_7d,
                "avg_daily_sales_30d": i.avg_daily_sales_30d,
                "days_remaining": i.days_remaining,
                "safety_stock": i.safety_stock,
                "lead_time_days": i.lead_time_days,
                "buffer_days": i.buffer_days,
                "in_transit": i.in_transit,
                "suggested_order": i.suggested_order,
                "alert_level": i.alert_level
            }
            for i in items
        ],
        "total": len(items)
    }


@router.get("/inventory/stats")
async def get_inventory_stats(
    db: Session = Depends(get_db)
):
    """库存统计"""
    total_skus = db.query(func.count(InventoryStatus.id)).scalar() or 0
    
    urgent = db.query(func.count(InventoryStatus.id)).filter(
        InventoryStatus.alert_level == 'red'
    ).scalar() or 0
    
    warning = db.query(func.count(InventoryStatus.id)).filter(
        InventoryStatus.alert_level == 'orange'
    ).scalar() or 0
    
    reminder = db.query(func.count(InventoryStatus.id)).filter(
        InventoryStatus.alert_level == 'blue'
    ).scalar() or 0
    
    safe = db.query(func.count(InventoryStatus.id)).filter(
        InventoryStatus.alert_level == 'green'
    ).scalar() or 0
    
    return {
        "total_skus": total_skus,
        "urgent": urgent,
        "warning": warning,
        "reminder": reminder,
        "safe": safe
    }


@router.get("/slow-moving")
async def get_slow_moving(
    status: Optional[str] = Query(None, description="状态"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """滞销清理"""
    query = db.query(SlowMoving)
    
    if status:
        query = query.filter(SlowMoving.status == status)
    
    items = query.order_by(desc(SlowMoving.age_days)).limit(limit).all()
    
    return {
        "items": [
            {
                "sku_id": s.sku_id,
                "product_id": s.product_id,
                "sku_name": s.sku_name,
                "inbound_date": s.inbound_date,
                "age_days": s.age_days,
                "sales_30d": s.sales_30d,
                "current_stock": s.current_stock,
                "status": s.status,
                "suggestion": s.suggestion
            }
            for s in items
        ],
        "total": len(items)
    }


@router.get("/slow-moving/stats")
async def get_slow_moving_stats(
    db: Session = Depends(get_db)
):
    """滞销统计"""
    total = db.query(func.count(SlowMoving.id)).scalar() or 0
    
    slow = db.query(func.count(SlowMoving.id)).filter(
        SlowMoving.status == 'slow'
    ).scalar() or 0
    
    dead = db.query(func.count(SlowMoving.id)).filter(
        SlowMoving.status == 'dead'
    ).scalar() or 0
    
    normal = db.query(func.count(SlowMoving.id)).filter(
        SlowMoving.status == 'normal'
    ).scalar() or 0
    
    avg_age = db.query(func.avg(SlowMoving.age_days)).scalar() or 0
    
    return {
        "total": total,
        "slow": slow,
        "dead": dead,
        "normal": normal,
        "avg_age_days": round(avg_age, 1)
    }


@router.post("/inventory/calculate")
async def calculate_inventory(
    db: Session = Depends(get_db)
):
    """计算库存预警"""
    items = db.query(InventoryStatus).all()
    
    updated = 0
    for item in items:
        if item.avg_daily_sales_30d > 0:
            item.days_remaining = item.current_stock / item.avg_daily_sales_30d
            item.suggested_order = max(0, int(
                item.safety_stock + 
                item.lead_time_days * item.avg_daily_sales_30d - 
                item.current_stock + 
                item.in_transit
            ))
            
            if item.days_remaining < 3:
                item.alert_level = 'red'
            elif item.days_remaining < 7:
                item.alert_level = 'orange'
            elif item.days_remaining < 14:
                item.alert_level = 'blue'
            else:
                item.alert_level = 'green'
            
            updated += 1
    
    db.commit()
    
    return {"success": True, "updated": updated}
