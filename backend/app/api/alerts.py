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


@router.get("/", response_model=dict)
@router.get("", response_model=dict)
def get_alerts(
    status: Optional[str] = Query(None, description="状态"),
    severity: Optional[str] = Query(None, description="级别"),
    alert_type: Optional[str] = Query(None, description="类型"),
    limit: int = Query(100, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if status == "dismissed":
        query = query.filter(Alert.dismissed == True)
    elif status == "active":
        query = query.filter(Alert.dismissed == False)

    total = query.count()
    alerts = query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()

    alert_list = []
    for a in alerts:
        alert_list.append({
            "id": a.id,
            "alert_date": a.alert_date,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "detail": a.detail,
            "metric_name": a.metric_name,
            "current_value": a.current_value,
            "target_value": a.target_value,
            "period": a.period,
            "dismissed": a.dismissed,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    return {"code": 200, "data": {"records": alert_list, "total": total}}


@router.get("/statistics", response_model=dict)
@router.get("/statistics/", response_model=dict)
def get_alert_statistics(days: int = Query(30, description="统计天数"), db: Session = Depends(get_db)):
    start_date = datetime.now() - timedelta(days=days)

    total = db.query(func.count(Alert.id)).scalar() or 0
    active = db.query(func.count(Alert.id)).filter(Alert.dismissed == False).scalar() or 0
    dismissed = db.query(func.count(Alert.id)).filter(Alert.dismissed == True).scalar() or 0
    high = db.query(func.count(Alert.id)).filter(Alert.severity == "high", Alert.dismissed == False).scalar() or 0
    medium = db.query(func.count(Alert.id)).filter(Alert.severity == "medium", Alert.dismissed == False).scalar() or 0

    type_query = db.query(Alert.alert_type, func.count(Alert.id).label("count")).group_by(Alert.alert_type).all()
    by_type = {r.alert_type: r.count for r in type_query}

    return {"code": 200, "data": {
        "total_alerts": total, "active": active, "dismissed": dismissed,
        "critical": high, "warning": medium, "by_type": by_type
    }}


@router.put("/{alert_id}/dismiss", response_model=dict)
def dismiss_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return {"code": 404, "message": "告警不存在"}

    alert.dismissed = True
    db.commit()
    return {"code": 200, "message": "告警已忽略"}


@router.put("/{alert_id}/reopen", response_model=dict)
def reopen_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return {"code": 404, "message": "告警不存在"}

    alert.dismissed = False
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


@router.get("/rules", response_model=dict)
@router.get("/rules/", response_model=dict)
def get_alert_rules(db: Session = Depends(get_db)):
    rules = db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
    rule_list = []
    for r in rules:
        rule_list.append({
            "id": r.id,
            "metric": r.metric,
            "operator": r.operator,
            "threshold": r.threshold,
            "level": r.level,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"code": 200, "data": rule_list}


@router.post("/rules", response_model=dict)
def create_alert_rule(
    metric: str = None,
    operator: str = None,
    threshold: float = None,
    level: str = None,
    enabled: bool = True,
    db: Session = Depends(get_db)
):
    new_rule = AlertRule(
        metric=metric,
        operator=operator,
        threshold=threshold,
        level=level,
        enabled=enabled
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return {"code": 200, "message": "告警规则创建成功", "data": {"id": new_rule.id}}


@router.delete("/rules/{rule_id}", response_model=dict)
def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        return {"code": 404, "message": "规则不存在"}
    db.delete(rule)
    db.commit()
    return {"code": 200, "message": "规则已删除"}


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

            if rule.operator == "gt" and current_value > rule.threshold:
                triggered = True
            elif rule.operator == "lt" and current_value < rule.threshold:
                triggered = True
            elif rule.operator == "gte" and current_value >= rule.threshold:
                triggered = True
            elif rule.operator == "lte" and current_value <= rule.threshold:
                triggered = True

            if triggered:
                existing = db.query(Alert).filter(
                    Alert.metric_name == rule.metric,
                    Alert.title.contains(product.title),
                    Alert.dismissed == False
                ).first()

                if not existing:
                    new_alert = Alert(
                        alert_date=datetime.now().strftime("%Y-%m-%d"),
                        alert_type=rule.metric,
                        severity=rule.level,
                        title=f"商品{product.title}的{rule.metric}指标异常",
                        detail=f"当前值{current_value}{rule.operator}{rule.threshold}",
                        metric_name=rule.metric,
                        current_value=current_value,
                        target_value=rule.threshold,
                        period=datetime.now().strftime("%Y-%m"),
                        dismissed=False
                    )
                    db.add(new_alert)
                    new_alert_count += 1

    db.commit()
    return {"code": 200, "message": f"已生成 {new_alert_count} 条新告警"}
