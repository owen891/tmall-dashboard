from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from app.core.database import get_db
from app.models import OperationAction, Product, WeeklyData
from app.schemas.common import ResponseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/operations", tags=["运营管理"])


def calculate_effectiveness(action: OperationAction) -> dict:
    """计算操作效果评分"""
    effects = []
    
    if action.before_payment and action.after_payment:
        payment_change = (action.after_payment - action.before_payment) / action.before_payment * 100
        effects.append({
            "metric": "销售额",
            "change": round(payment_change, 2),
            "direction": "up" if payment_change > 0 else "down",
            "weight": 0.3
        })
    
    if action.before_visitors and action.after_visitors:
        visitor_change = (action.after_visitors - action.before_visitors) / action.before_visitors * 100
        effects.append({
            "metric": "访客数",
            "change": round(visitor_change, 2),
            "direction": "up" if visitor_change > 0 else "down",
            "weight": 0.2
        })
    
    if action.before_conversion and action.after_conversion:
        conversion_change = (action.after_conversion - action.before_conversion) / action.before_conversion * 100
        effects.append({
            "metric": "转化率",
            "change": round(conversion_change, 2),
            "direction": "up" if conversion_change > 0 else "down",
            "weight": 0.25
        })
    
    if action.before_roi and action.after_roi:
        roi_change = (action.after_roi - action.before_roi) / action.before_roi * 100
        effects.append({
            "metric": "ROI",
            "change": round(roi_change, 2),
            "direction": "up" if roi_change > 0 else "down",
            "weight": 0.25
        })
    
    positive_count = sum(1 for e in effects if e["direction"] == "up")
    total_weight = sum(e["weight"] for e in effects)
    
    if total_weight == 0:
        return {"score": 50, "effects": effects, "positive_count": 0, "total_count": 0}
    
    score = 50 + (positive_count / len(effects) * 50 - 50) * (total_weight / 0.3)
    score = max(0, min(100, score))
    
    return {
        "score": round(score, 1),
        "effects": effects,
        "positive_count": positive_count,
        "total_count": len(effects)
    }


@router.get("/", response_model=ResponseModel)
def get_operations(
    product_id: Optional[str] = None,
    action_type: Optional[str] = None,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取操作记录列表"""
    
    query = db.query(OperationAction)
    
    if product_id:
        query = query.filter(OperationAction.product_id == product_id)
    if action_type:
        query = query.filter(OperationAction.action_type == action_type)
    
    total = query.count()
    operations = query.order_by(desc(OperationAction.action_date)).offset(offset).limit(limit).all()
    
    result = []
    for op in operations:
        product = db.query(Product).filter(Product.product_id == op.product_id).first()
        
        effectiveness = {
            "score": op.effectiveness_score or 0,
            "effects": []
        }
        
        if op.before_payment and op.after_payment:
            change = (op.after_payment - op.before_payment) / op.before_payment * 100 if op.before_payment else 0
            effectiveness["effects"].append({
                "metric": "销售额",
                "before": op.before_payment,
                "after": op.after_payment,
                "change": round(change, 2),
                "direction": "up" if change > 0 else "down"
            })
        
        if op.before_visitors and op.after_visitors:
            change = (op.after_visitors - op.before_visitors) / op.before_visitors * 100 if op.before_visitors else 0
            effectiveness["effects"].append({
                "metric": "访客数",
                "before": op.before_visitors,
                "after": op.after_visitors,
                "change": round(change, 2),
                "direction": "up" if change > 0 else "down"
            })
        
        if op.before_conversion and op.after_conversion:
            change = (op.after_conversion - op.before_conversion) / op.before_conversion * 100 if op.before_conversion else 0
            effectiveness["effects"].append({
                "metric": "转化率",
                "before": op.before_conversion,
                "after": op.after_conversion,
                "change": round(change, 2),
                "direction": "up" if change > 0 else "down"
            })
        
        if op.before_roi and op.after_roi:
            change = (op.after_roi - op.before_roi) / op.before_roi * 100 if op.before_roi else 0
            effectiveness["effects"].append({
                "metric": "ROI",
                "before": op.before_roi,
                "after": op.after_roi,
                "change": round(change, 2),
                "direction": "up" if change > 0 else "down"
            })
        
        result.append({
            "id": op.id,
            "product_id": op.product_id,
            "product_title": product.title if product else None,
            "action_date": op.action_date.isoformat() if op.action_date else None,
            "action_type": op.action_type,
            "action_detail": op.action_detail,
            "effectiveness": effectiveness
        })
    
    return ResponseModel(data={
        "operations": result,
        "total": total,
        "limit": limit,
        "offset": offset
    })


@router.post("/", response_model=ResponseModel)
def create_operation(
    product_id: str,
    action_type: str,
    action_date: str,
    action_detail: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """创建操作记录（自动获取操作前后数据）"""
    from datetime import datetime as dt
    
    action_date_obj = dt.strptime(action_date, "%Y-%m-%d").date()
    prev_date = action_date_obj - timedelta(days=7)
    
    current_week = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id,
        WeeklyData.week_start == action_date_obj
    ).first()
    
    prev_week = db.query(WeeklyData).filter(
        WeeklyData.product_id == product_id,
        WeeklyData.week_start == prev_date
    ).first()
    
    operation = OperationAction(
        product_id=product_id,
        action_date=action_date_obj,
        action_type=action_type,
        action_detail=action_detail,
        before_payment=prev_week.payment_amount if prev_week else 0,
        before_visitors=prev_week.ipv if prev_week else 0,
        before_conversion=prev_week.payment_conversion if prev_week else 0,
        before_roi=prev_week.ad_roi if prev_week else 0,
        after_payment=current_week.payment_amount if current_week else 0,
        after_visitors=current_week.ipv if current_week else 0,
        after_conversion=current_week.payment_conversion if current_week else 0,
        after_roi=current_week.ad_roi if current_week else 0
    )
    
    db.add(operation)
    db.commit()
    db.refresh(operation)
    
    effectiveness = calculate_effectiveness(operation)
    operation.effectiveness_score = effectiveness["score"]
    db.commit()
    
    return ResponseModel(data={
        "message": "操作记录已创建",
        "operation": {
            "id": operation.id,
            "product_id": operation.product_id,
            "action_date": operation.action_date.isoformat(),
            "action_type": operation.action_type,
            "effectiveness_score": operation.effectiveness_score
        },
        "effectiveness": effectiveness
    })


@router.get("/statistics", response_model=ResponseModel)
def get_operation_statistics(
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取操作效果统计"""
    
    query = db.query(OperationAction)
    
    if period:
        try:
            period_date = datetime.strptime(period, "%Y-%m-%d").date()
            start_date = period_date - timedelta(days=30)
            query = query.filter(
                OperationAction.action_date >= start_date,
                OperationAction.action_date <= period_date
            )
        except:
            pass
    
    operations = query.all()
    
    if not operations:
        return ResponseModel(data={
            "total_operations": 0,
            "by_type": {},
            "avg_effectiveness": 0,
            "top_performers": []
        })
    
    by_type = {}
    total_effectiveness = 0
    positive_count = 0
    
    for op in operations:
        if op.action_type not in by_type:
            by_type[op.action_type] = {"count": 0, "total_score": 0, "positive": 0}
        
        by_type[op.action_type]["count"] += 1
        by_type[op.action_type]["total_score"] += op.effectiveness_score or 0
        
        if op.effectiveness_score and op.effectiveness_score > 50:
            by_type[op.action_type]["positive"] += 1
            positive_count += 1
        
        total_effectiveness += op.effectiveness_score or 0
    
    for action_type, stats in by_type.items():
        stats["avg_score"] = round(stats["total_score"] / stats["count"], 1) if stats["count"] > 0 else 0
        stats["positive_rate"] = round(stats["positive"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0
    
    top_performers = []
    sorted_ops = sorted(operations, key=lambda x: x.effectiveness_score or 0, reverse=True)[:10]
    
    for op in sorted_ops:
        product = db.query(Product).filter(Product.product_id == op.product_id).first()
        top_performers.append({
            "product_id": op.product_id,
            "product_title": product.title if product else None,
            "action_type": op.action_type,
            "action_date": op.action_date.isoformat() if op.action_date else None,
            "effectiveness_score": op.effectiveness_score
        })
    
    return ResponseModel(data={
        "total_operations": len(operations),
        "by_type": by_type,
        "avg_effectiveness": round(total_effectiveness / len(operations), 1),
        "positive_rate": round(positive_count / len(operations) * 100, 1),
        "top_performers": top_performers
    })


@router.delete("/{operation_id}", response_model=ResponseModel)
def delete_operation(operation_id: int, db: Session = Depends(get_db)):
    """删除操作记录"""
    operation = db.query(OperationAction).filter(OperationAction.id == operation_id).first()
    
    if not operation:
        return ResponseModel(data={"message": "操作记录不存在"})
    
    db.delete(operation)
    db.commit()
    
    return ResponseModel(data={"message": "操作记录已删除"})
