from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_
from typing import Optional, List
from app.core.database import get_db
from app.models.command_tower import (
    SmartAlertRule, SmartAlert, SupplyChainData, InventoryAlert
)
from app.models.product import Product, DailyData
from app.schemas.common import ResponseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/smart-alert", tags=["智能告警"])


@router.get("/rules", response_model=ResponseModel)
def get_alert_rules(
    metric: Optional[str] = None,
    level: Optional[str] = None,
    only_enabled: bool = True,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取告警规则列表"""
    query = db.query(SmartAlertRule)
    if only_enabled:
        query = query.filter(SmartAlertRule.enabled == True)
    if metric:
        query = query.filter(SmartAlertRule.metric == metric)
    if level:
        query = query.filter(SmartAlertRule.level == level)
    
    total = query.count()
    rules = query.order_by(desc(SmartAlertRule.created_at)).offset(offset).limit(limit).all()
    
    return ResponseModel(data={
        "rules": [{
            "id": r.id,
            "rule_name": r.rule_name,
            "rule_type": r.rule_type,
            "metric": r.metric,
            "metric_label": r.metric_label,
            "condition_type": r.condition_type,
            "operator": r.operator,
            "threshold": r.threshold,
            "window_type": r.window_type,
            "window_size": r.window_size,
            "level": r.level,
            "enabled": r.enabled,
            "created_by": r.created_by
        } for r in rules],
        "total": total
    })


@router.post("/rules", response_model=ResponseModel)
def create_alert_rule(
    rule_name: str,
    metric: str,
    condition_type: str = "threshold",
    operator: str = ">",
    threshold: float = 0,
    level: str = "warning",
    window_type: str = "consecutive",
    window_size: int = 2,
    product_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """创建告警规则"""
    rule = SmartAlertRule(
        rule_name=rule_name,
        metric=metric,
        condition_type=condition_type,
        operator=operator,
        threshold=threshold,
        level=level,
        window_type=window_type,
        window_size=window_size,
        product_id=product_id,
        enabled=True,
        is_active=True
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return ResponseModel(data={"id": rule.id, "message": "告警规则创建成功"})


@router.post("/rules/{rule_id}", response_model=ResponseModel)
def toggle_rule(
    rule_id: int,
    enabled: bool = True,
    db: Session = Depends(get_db)
):
    """启用/禁用告警规则"""
    rule = db.query(SmartAlertRule).filter(SmartAlertRule.id == rule_id).first()
    if not rule:
        return ResponseModel(code=404, message="规则不存在")
    
    rule.enabled = enabled
    db.commit()
    
    return ResponseModel(data={"message": f"规则已{'启用' if enabled else '禁用'}"})


@router.get("/alerts", response_model=ResponseModel)
def get_alerts(
    level: Optional[str] = None,
    status: Optional[str] = None,
    product_id: Optional[str] = None,
    only_unresolved: bool = False,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取告警列表"""
    query = db.query(SmartAlert)
    if level:
        query = query.filter(SmartAlert.level == level)
    if product_id:
        query = query.filter(SmartAlert.product_id == product_id)
    if only_unresolved:
        query = query.filter(SmartAlert.resolved == False)
    if status == "unread":
        query = query.filter(SmartAlert.dismissed == False)
    
    total = query.count()
    alerts = query.order_by(desc(SmartAlert.created_at)).offset(offset).limit(limit).all()
    
    return ResponseModel(data={
        "alerts": [{
            "id": a.id,
            "rule_id": a.rule_id,
            "alert_type": a.alert_type,
            "title": a.title,
            "detail": a.detail,
            "product_id": a.product_id,
            "product_title": a.product_title,
            "metric": a.metric,
            "current_value": a.current_value,
            "threshold_value": a.threshold_value,
            "change_percent": a.change_percent,
            "level": a.level,
            "severity": a.severity,
            "dismissed": a.dismissed,
            "resolved": a.resolved,
            "recommendations": a.recommendations,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in alerts],
        "total": total
    })


@router.post("/alerts/{alert_id}/dismiss", response_model=ResponseModel)
def dismiss_alert(
    alert_id: int,
    dismiss_note: str = "",
    db: Session = Depends(get_db)
):
    """忽略告警"""
    alert = db.query(SmartAlert).filter(SmartAlert.id == alert_id).first()
    if not alert:
        return ResponseModel(code=404, message="告警不存在")
    
    alert.dismissed = True
    alert.dismiss_note = dismiss_note
    alert.dismissed_at = datetime.now()
    db.commit()
    
    return ResponseModel(data={"message": "告警已忽略"})


@router.post("/alerts/{alert_id}/resolve", response_model=ResponseModel)
def resolve_alert(
    alert_id: int,
    action_taken: str = "",
    db: Session = Depends(get_db)
):
    """解决告警"""
    alert = db.query(SmartAlert).filter(SmartAlert.id == alert_id).first()
    if not alert:
        return ResponseModel(code=404, message="告警不存在")
    
    alert.resolved = True
    alert.action_taken = action_taken
    alert.resolved_at = datetime.now()
    db.commit()
    
    return ResponseModel(data={"message": "告警已解决"})


def check_threshold_condition(value, operator, threshold):
    """检查阈值条件"""
    if operator == ">":
        return value > threshold
    elif operator == ">=":
        return value >= threshold
    elif operator == "<":
        return value < threshold
    elif operator == "<=":
        return value <= threshold
    elif operator == "==":
        return value == threshold
    return False


@router.post("/check", response_model=ResponseModel)
def check_and_generate_alerts(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """检查并生成告警（可异步执行）"""
    rules = db.query(SmartAlertRule).filter(SmartAlertRule.enabled == True).all()
    
    new_alerts = []
    for rule in rules:
        product_ids = []
        if rule.product_id:
            product_ids = [rule.product_id]
        elif rule.product_ids:
            product_ids = rule.product_ids if isinstance(rule.product_ids, list) else []
        else:
            products = db.query(Product.product_id).all()
            product_ids = [p[0] for p in products]
        
        for product_id in product_ids:
            product = db.query(Product).filter(Product.product_id == product_id).first()
            
            # 获取最近数据
            recent_data = db.query(DailyData).filter(
                DailyData.product_id == product_id
            ).order_by(desc(DailyData.date)).limit(rule.window_size).all()
            
            if len(recent_data) < rule.window_size:
                continue
            
            # 检查是否触发
            triggered = False
            values = []
            metric_name = ""
            
            for data in recent_data:
                # 获取指标值
                value = 0
                if rule.metric == "payment_amount":
                    value = data.payment_amount
                    metric_name = "销售额"
                elif rule.metric == "payment_conversion":
                    value = data.payment_conversion
                    metric_name = "转化率"
                elif rule.metric == "ctr":
                    value = getattr(data, "ctr", 0)
                    metric_name = "点击率"
                elif rule.metric == "uv_value":
                    value = data.uv_value
                    metric_name = "UV价值"
                elif rule.metric == "refund_amount":
                    value = data.refund_amount
                    metric_name = "退款金额"
                values.append(value)
            
            # 连续触发
            if rule.window_type == "consecutive":
                all_triggered = all(
                    check_threshold_condition(v, rule.operator, rule.threshold)
                    for v in values
                )
                if all_triggered:
                    triggered = True
            
            # 检查是否重复报警
            if triggered:
                recent_alert = db.query(SmartAlert).filter(
                    and_(
                        SmartAlert.rule_id == rule.id,
                        SmartAlert.product_id == product_id,
                        SmartAlert.created_at >= datetime.now() - timedelta(hours=24)
                    )
                ).first()
                
                if not recent_alert:
                    # 创建新告警
                    alert = SmartAlert(
                        rule_id=rule.id,
                        product_id=product_id,
                        product_title=product.title if product else "",
                        metric=rule.metric,
                        metric_label=metric_name,
                        current_value=values[0],
                        threshold_value=rule.threshold,
                        level=rule.level,
                        severity=rule.severity or "medium",
                        title=f"{metric_name}异常",
                        detail=f"{metric_name}连续{rule.window_size}天触发阈值条件",
                        alert_type=rule.rule_type or "threshold",
                        recommendations=["检查数据异常原因", "评估运营策略", "制定优化方案"],
                        created_at=datetime.now()
                    )
                    db.add(alert)
                    new_alerts.append(alert)
    
    db.commit()
    
    return ResponseModel(data={
        "message": "检查完成",
        "new_alerts": len(new_alerts),
        "alerts": [{
            "id": a.id,
            "product_id": a.product_id,
            "title": a.title
        } for a in new_alerts]
    })


@router.get("/supply-chain", response_model=ResponseModel)
def get_supply_chain_alerts(
    db: Session = Depends(get_db)
):
    """获取供应链告警"""
    alerts = db.query(InventoryAlert).order_by(desc(InventoryAlert.created_at)).all()
    
    return ResponseModel(data={
        "alerts": [{
            "id": a.id,
            "product_id": a.product_id,
            "alert_type": a.alert_type,
            "title": a.title,
            "detail": a.detail,
            "current_stock": a.current_stock,
            "level": a.level,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in alerts]
    })

