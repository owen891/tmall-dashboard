from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.core.database import get_db
from app.models.alerts import AlertRule
from app.models.dashboard_models import AlertRecord

router = APIRouter(prefix="/alerts", tags=["告警规则"])


class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    operator: str = ">"
    threshold: float
    level: str = "warning"
    enabled: bool = True


class AlertRecordUpdate(BaseModel):
    status: Optional[str] = None
    handler: Optional[str] = None


@router.get("/rules")
async def get_alert_rules(
    enabled: Optional[bool] = Query(None, description="是否启用"),
    level: Optional[str] = Query(None, description="级别"),
    db: Session = Depends(get_db)
):
    """告警规则列表"""
    query = db.query(AlertRule)
    
    if enabled is not None:
        query = query.filter(AlertRule.enabled == enabled)
    if level:
        query = query.filter(AlertRule.level == level)
    
    rules = query.order_by(AlertRule.id.desc()).all()
    
    return {
        "items": [
            {
                "rule_id": r.id,
                "name": r.name,
                "metric": r.metric,
                "operator": r.operator,
                "threshold": r.threshold,
                "level": r.level,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in rules
        ],
        "total": len(rules)
    }


@router.post("/rules")
async def create_alert_rule(
    rule: AlertRuleCreate,
    db: Session = Depends(get_db)
):
    """创建告警规则"""
    db_rule = AlertRule(
        name=rule.name,
        metric=rule.metric,
        operator=rule.operator,
        threshold=rule.threshold,
        level=rule.level,
        enabled=rule.enabled
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return {"rule_id": db_rule.id, "success": True}


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    rule: AlertRuleCreate,
    db: Session = Depends(get_db)
):
    """更新告警规则"""
    db_rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    db_rule.name = rule.name
    db_rule.metric = rule.metric
    db_rule.operator = rule.operator
    db_rule.threshold = rule.threshold
    db_rule.level = rule.level
    db_rule.enabled = rule.enabled
    
    db.commit()
    
    return {"success": True}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """删除告警规则"""
    db_rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    db.delete(db_rule)
    db.commit()
    
    return {"success": True}


@router.get("/records")
async def get_alert_records(
    status: Optional[str] = Query(None, description="状态"),
    level: Optional[str] = Query(None, description="级别"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """告警记录"""
    query = db.query(AlertRecord)
    
    if status:
        query = query.filter(AlertRecord.status == status)
    if level:
        query = query.filter(AlertRecord.level == level)
    
    records = query.order_by(AlertRecord.id.desc()).limit(limit).all()
    
    return {
        "items": [
            {
                "record_id": r.id,
                "rule_id": r.rule_id,
                "title": r.title,
                "detail": r.detail,
                "current_value": r.current_value,
                "threshold_value": r.threshold_value,
                "status": r.status,
                "handler": r.handler,
                "level": r.level,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ],
        "total": len(records)
    }


@router.put("/records/{record_id}")
async def update_alert_record(
    record_id: int,
    update: AlertRecordUpdate,
    db: Session = Depends(get_db)
):
    """更新告警记录"""
    db_record = db.query(AlertRecord).filter(AlertRecord.id == record_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    if update.status:
        db_record.status = update.status
    if update.handler:
        db_record.handler = update.handler
    
    db.commit()
    
    return {"success": True}


@router.get("/stats")
async def get_alert_stats(
    db: Session = Depends(get_db)
):
    """告警统计"""
    total = db.query(func.count(AlertRecord.id)).scalar() or 0
    pending = db.query(func.count(AlertRecord.id)).filter(
        AlertRecord.status == 'pending'
    ).scalar() or 0
    handling = db.query(func.count(AlertRecord.id)).filter(
        AlertRecord.status == 'handling'
    ).scalar() or 0
    resolved = db.query(func.count(AlertRecord.id)).filter(
        AlertRecord.status == 'resolved'
    ).scalar() or 0
    
    urgent = db.query(func.count(AlertRecord.id)).filter(
        AlertRecord.level == 'urgent'
    ).scalar() or 0
    
    return {
        "total": total,
        "pending": pending,
        "handling": handling,
        "resolved": resolved,
        "urgent": urgent
    }
