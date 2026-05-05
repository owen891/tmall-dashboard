from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.alerts import Alert, AlertRule
from app.models import Product

router = APIRouter(prefix="/alerts", tags=["告警管理"])

class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    condition: str
    threshold: float
    severity: str
    enabled: bool = True

class AlertRuleResponse(BaseModel):
    id: int
    name: str
    metric: str
    condition: str
    threshold: float
    severity: str
    enabled: bool
    created_at: str

class AlertCreate(BaseModel):
    rule_id: Optional[int] = None
    product_id: Optional[int] = None
    product_name: str
    alert_type: str
    severity: str
    metric: str
    current_value: float
    threshold: float
    message: str

class AlertResponse(BaseModel):
    id: int
    rule_id: Optional[int] = None
    product_id: Optional[int] = None
    product_name: str
    alert_type: str
    severity: str
    metric: str
    current_value: float
    threshold: float
    message: str
    status: str
    created_at: str
    resolved_at: Optional[str] = None

class AlertStats(BaseModel):
    total_alerts: int
    unresolved: int
    resolved: int
    critical: int
    warning: int
    by_type: dict


@router.get("/rules", response_model=dict)
def get_alert_rules(db: Session = Depends(get_db)):
    rules = db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
    rule_list = []
    for r in rules:
        rule_list.append(AlertRuleResponse(
            id=r.id,
            name=r.name,
            metric=r.metric,
            condition=r.condition,
            threshold=r.threshold,
            severity=r.severity,
            enabled=r.enabled,
            created_at=r.created_at.isoformat() if r.created_at else ""
        ))
    return {"code": 200, "data": rule_list}


@router.post("/rules", response_model=dict)
def create_alert_rule(rule: AlertRuleCreate, db: Session = Depends(get_db)):
    new_rule = AlertRule(
        name=rule.name,
        metric=rule.metric,
        condition=rule.condition,
        threshold=rule.threshold,
        severity=rule.severity,
        enabled=rule.enabled
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return {"code": 200, "message": "告警规则创建成功", "data": {"id": new_rule.id}}


@router.put("/rules/{rule_id}", response_model=dict)
def update_alert_rule(rule_id: int, rule: AlertRuleCreate, db: Session = Depends(get_db)):
    rule_obj = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule_obj:
        return {"code": 404, "message": "规则不存在"}
    
    rule_obj.name = rule.name
    rule_obj.metric = rule.metric
    rule_obj.condition = rule.condition
    rule_obj.threshold = rule.threshold
    rule_obj.severity = rule.severity
    rule_obj.enabled = rule.enabled
    
    db.commit()
    return {"code": 200, "message": "规则已更新"}


@router.delete("/rules/{rule_id}", response_model=dict)
def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        return {"code": 404, "message": "规则不存在"}
    db.delete(rule)
    db.commit()
    return {"code": 200, "message": "规则已删除"}


@router.get("/", response_model=dict)
def get_alerts(
    status: Optional[str] = Query(None, description="状态: unresolved/resolved/all"),
    severity: Optional[str] = Query(None, description="级别: critical/warning/info"),
    alert_type: Optional[str] = Query(None, description="类型"),
    product_id: Optional[int] = None,
    limit: int = Query(100, description="返回数量"),
    db: Session = Depends(get_db)
):
    query = db.query(Alert)
    
    if status and status != "all":
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if product_id:
        query = query.filter(Alert.product_id == product_id)
    
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    
    alert_list = []
    for a in alerts:
        alert_list.append(AlertResponse(
            id=a.id,
            rule_id=a.rule_id,
            product_id=a.product_id,
            product_name=a.product_name,
            alert_type=a.alert_type,
            severity=a.severity,
            metric=a.metric,
            current_value=a.current_value,
            threshold=a.threshold,
            message=a.message,
            status=a.status,
            created_at=a.created_at.isoformat() if a.created_at else "",
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None
        ))
    
    return {"code": 200, "data": alert_list}


@router.post("/", response_model=dict)
def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    new_alert = Alert(
        rule_id=alert.rule_id,
        product_id=alert.product_id,
        product_name=alert.product_name,
        alert_type=alert.alert_type,
        severity=alert.severity,
        metric=alert.metric,
        current_value=alert.current_value,
        threshold=alert.threshold,
        message=alert.message,
        status="unresolved"
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return {"code": 200, "message": "告警已创建", "data": {"id": new_alert.id}}


@router.put("/{alert_id}/resolve", response_model=dict)
def resolve_alert(alert_id: int, resolution_note: Optional[str] = None, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return {"code": 404, "message": "告警不存在"}
    
    alert.status = "resolved"
    alert.resolved_at = datetime.now()
    if resolution_note:
        alert.message = f"{alert.message}\n[处理备注] {resolution_note}"
    
    db.commit()
    return {"code": 200, "message": "告警已标记为已处理"}


@router.put("/{alert_id}/reopen", response_model=dict)
def reopen_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return {"code": 404, "message": "告警不存在"}
    
    alert.status = "unresolved"
    alert.resolved_at = None
    db.commit()
    return {"code": 200, "message": "告警已重新打开"}


@router.delete("/{alert_id}", response_model=dict)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return {"code": 404, "message": "告警不存在"}
    db.delete(alert)
    db.commit()
    return {"code": 200, "message": "告警已删除"}


@router.post("/bulk/resolve", response_model=dict)
def bulk_resolve_alerts(alert_ids: List[int], db: Session = Depends(get_db)):
    db.query(Alert).filter(Alert.id.in_(alert_ids)).update(
        {"status": "resolved", "resolved_at": datetime.now()},
        synchronize_session=False
    )
    db.commit()
    return {"code": 200, "message": f"已处理 {len(alert_ids)} 条告警"}


@router.get("/statistics", response_model=dict)
def get_alert_statistics(days: int = Query(30, description="统计天数"), db: Session = Depends(get_db)):
    start_date = datetime.now() - timedelta(days=days)
    
    total = db.query(func.count(Alert.id)).filter(Alert.created_at >= start_date).scalar() or 0
    unresolved = db.query(func.count(Alert.id)).filter(Alert.created_at >= start_date, Alert.status == "unresolved").scalar() or 0
    resolved = db.query(func.count(Alert.id)).filter(Alert.created_at >= start_date, Alert.status == "resolved").scalar() or 0
    critical = db.query(func.count(Alert.id)).filter(Alert.created_at >= start_date, Alert.severity == "critical", Alert.status == "unresolved").scalar() or 0
    warning = db.query(func.count(Alert.id)).filter(Alert.created_at >= start_date, Alert.severity == "warning", Alert.status == "unresolved").scalar() or 0
    
    type_query = db.query(Alert.alert_type, func.count(Alert.id).label("count")).filter(Alert.created_at >= start_date).group_by(Alert.alert_type).all()
    by_type = {r.alert_type: r.count for r in type_query}
    
    return {"code": 200, "data": {
        "total_alerts": total, "unresolved": unresolved, "resolved": resolved,
        "critical": critical, "warning": warning, "by_type": by_type
    }}


@router.post("/generate", response_model=dict)
def generate_alerts_from_rules(db: Session = Depends(get_db)):
    rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()
    products = db.query(Product).all()
    new_alert_count = 0
    
    for rule in rules:
        for product in products:
            current_value = 0
            metric_field = None
            
            if rule.metric == "gmv":
                metric_field = getattr(product, "gmv", None)
            elif rule.metric == "refund_rate":
                metric_field = getattr(product, "refund_rate", None)
            elif rule.metric == "roi":
                metric_field = getattr(product, "total_roi", None)
            elif rule.metric == "conversion":
                metric_field = getattr(product, "conversion", None)
            elif rule.metric == "visitors":
                metric_field = getattr(product, "visitors", None)
            
            if metric_field is None:
                continue
            
            current_value = float(metric_field or 0)
            triggered = False
            
            if rule.condition == "gt" and current_value > rule.threshold:
                triggered = True
            elif rule.condition == "lt" and current_value < rule.threshold:
                triggered = True
            elif rule.condition == "eq" and abs(current_value - rule.threshold) < 0.001:
                triggered = True
            elif rule.condition == "gte" and current_value >= rule.threshold:
                triggered = True
            elif rule.condition == "lte" and current_value <= rule.threshold:
                triggered = True
            
            if triggered:
                existing = db.query(Alert).filter(
                    Alert.rule_id == rule.id,
                    Alert.product_id == product.id,
                    Alert.status == "unresolved"
                ).first()
                
                if not existing:
                    message = f"商品{product.title}的{rule.metric}指标({current_value}){rule.condition}{rule.threshold}"
                    new_alert = Alert(
                        rule_id=rule.id,
                        product_id=product.id,
                        product_name=product.title,
                        alert_type=rule.metric,
                        severity=rule.severity,
                        metric=rule.metric,
                        current_value=current_value,
                        threshold=rule.threshold,
                        message=message,
                        status="unresolved"
                    )
                    db.add(new_alert)
                    new_alert_count += 1
    
    db.commit()
    return {"code": 200, "message": f"已生成 {new_alert_count} 条新告警"}
