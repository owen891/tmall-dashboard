from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.models import Product, OperationLog, ProductNote

router = APIRouter(prefix="/collaboration", tags=["协作功能"])


@router.get("/team", response_model=ResponseModel)
def get_team_members(db: Session = Depends(get_db)):
    """
    获取团队成员列表
    """
    members = db.query(
        Product.manager,
        func.count(Product.id).label('product_count')
    ).filter(
        Product.manager.isnot(None),
        Product.manager != ''
    ).group_by(Product.manager).all()
    
    team_list = []
    for m in members:
        team_list.append({
            "name": m.manager,
            "role": "运营",
            "product_count": m.product_count
        })
    
    team_list.append({
        "name": "admin",
        "role": "管理员",
        "product_count": db.query(Product).filter(Product.status == 'active').count()
    })
    
    return ResponseModel(data={
        "total": len(team_list),
        "members": team_list
    })


@router.get("/activity-log", response_model=ResponseModel)
def get_activity_log(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    获取操作日志
    """
    logs = db.query(OperationLog).order_by(
        desc(OperationLog.created_at)
    ).limit(limit).all()
    
    log_list = []
    for log in logs:
        log_list.append({
            "id": log.id,
            "action": log.action,
            "detail": log.detail,
            "operator": log.operator,
            "created_at": log.created_at.isoformat() if log.created_at else None
        })
    
    return ResponseModel(data={
        "total": len(log_list),
        "logs": log_list
    })


@router.post("/activity-log", response_model=ResponseModel)
def create_activity_log(
    action: str,
    detail: str,
    operator: str = "system",
    db: Session = Depends(get_db)
):
    """
    创建操作日志
    """
    new_log = OperationLog(
        action=action,
        detail=detail,
        operator=operator
    )
    db.add(new_log)
    db.commit()
    
    return ResponseModel(data={
        "id": new_log.id,
        "message": "日志创建成功"
    })


@router.get("/notes", response_model=ResponseModel)
def get_product_notes(
    product_id: str = Query(..., description="商品ID"),
    db: Session = Depends(get_db)
):
    """
    获取商品备注列表
    """
    notes = db.query(ProductNote).filter(
        ProductNote.product_id == product_id
    ).order_by(desc(ProductNote.created_at)).all()
    
    note_list = []
    for note in notes:
        note_list.append({
            "id": note.id,
            "product_id": note.product_id,
            "note": note.note,
            "created_by": note.created_by,
            "created_at": note.created_at.isoformat() if note.created_at else None
        })
    
    return ResponseModel(data={
        "total": len(note_list),
        "notes": note_list
    })


@router.post("/notes", response_model=ResponseModel)
def create_product_note(
    product_id: str,
    note: str,
    created_by: str = "admin",
    db: Session = Depends(get_db)
):
    """
    创建商品备注
    """
    new_note = ProductNote(
        product_id=product_id,
        note=note,
        created_by=created_by
    )
    db.add(new_note)
    db.commit()
    
    return ResponseModel(data={
        "id": new_note.id,
        "message": "备注创建成功"
    })


@router.get("/workload", response_model=ResponseModel)
def get_workload_distribution(db: Session = Depends(get_db)):
    """
    获取工作量分布
    """
    workload = db.query(
        Product.manager,
        func.count(Product.id).label('total'),
        func.sum(Product.payment_amount).label('total_gmv')
    ).filter(
        Product.manager.isnot(None),
        Product.manager != '',
        Product.status == 'active'
    ).group_by(Product.manager).all()
    
    distribution = []
    for w in workload:
        distribution.append({
            "manager": w.manager,
            "product_count": w.total,
            "total_gmv": round(w.total_gmv or 0, 2),
            "avg_gmv": round((w.total_gmv or 0) / w.total, 2) if w.total > 0 else 0
        })
    
    distribution.sort(key=lambda x: x['total_gmv'], reverse=True)
    
    return ResponseModel(data={
        "total_managers": len(distribution),
        "distribution": distribution
    })


@router.get("/statistics", response_model=ResponseModel)
def get_collaboration_statistics(db: Session = Depends(get_db)):
    """
    获取协作统计
    """
    total_products = db.query(Product).filter(Product.status == 'active').count()
    total_notes = db.query(ProductNote).count()
    total_logs = db.query(OperationLog).count()
    
    active_managers = db.query(Product.manager).filter(
        Product.manager.isnot(None),
        Product.manager != ''
    ).distinct().count()
    
    recent_logs = db.query(OperationLog).order_by(
        desc(OperationLog.created_at)
    ).limit(10).all()
    
    return ResponseModel(data={
        "total_products": total_products,
        "total_notes": total_notes,
        "total_logs": total_logs,
        "active_managers": active_managers,
        "recent_activities": [{
            "action": log.action,
            "detail": log.detail[:50] + "..." if log.detail and len(log.detail) > 50 else log.detail,
            "operator": log.operator,
            "created_at": log.created_at.isoformat() if log.created_at else None
        } for log in recent_logs]
    })
