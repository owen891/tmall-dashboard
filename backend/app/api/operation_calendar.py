from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel
from app.core.database import get_db
from app.models.calendar import OperationCalendar
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/operation-calendar", tags=["运营日历"])

class CalendarEventCreate(BaseModel):
    event_date: str
    event_type: str
    title: str
    description: Optional[str] = None
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    operator: Optional[str] = None
    tags: Optional[str] = None
    budget: Optional[float] = 0
    status: Optional[str] = "planned"
    priority: Optional[str] = "medium"
    repeat_type: Optional[str] = None

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    metrics_after: Optional[str] = None
    payment_after: Optional[float] = None
    visitors_after: Optional[int] = None
    conversion_after: Optional[float] = None
    ad_spend_after: Optional[float] = None
    actual_cost: Optional[float] = None
    roi: Optional[float] = None
    effectiveness_score: Optional[int] = None
    follow_up: Optional[str] = None

@router.get("/events", response_model=ResponseModel)
def get_calendar_events(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    event_type: Optional[str] = Query(None, description="事件类型"),
    status: Optional[str] = Query(None, description="状态"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    db: Session = Depends(get_db)
):
    """获取运营日历事件列表"""
    query = db.query(OperationCalendar)
    
    if start_date:
        query = query.filter(OperationCalendar.event_date >= start_date)
    if end_date:
        query = query.filter(OperationCalendar.event_date <= end_date)
    if event_type:
        query = query.filter(OperationCalendar.event_type == event_type)
    if status:
        query = query.filter(OperationCalendar.status == status)
    if product_id:
        query = query.filter(OperationCalendar.product_id == product_id)
    
    events = query.order_by(OperationCalendar.event_date.desc()).all()
    
    result = []
    for e in events:
        result.append({
            "id": e.id,
            "event_date": str(e.event_date),
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description,
            "product_id": e.product_id,
            "product_name": e.product_name,
            "operator": e.operator,
            "tags": e.tags,
            "status": e.status,
            "priority": e.priority,
            "budget": e.budget,
            "actual_cost": e.actual_cost,
            "roi": e.roi,
            "effectiveness_score": e.effectiveness_score,
            "payment_before": e.payment_before,
            "payment_after": e.payment_after,
            "visitors_before": e.visitors_before,
            "visitors_after": e.visitors_after,
            "conversion_before": e.conversion_before,
            "conversion_after": e.conversion_after,
            "follow_up": e.follow_up,
            "created_at": str(e.created_at) if e.created_at else "",
        })
    
    return ResponseModel(data={"events": result, "total": len(result)})

@router.post("/events", response_model=ResponseModel)
def create_calendar_event(event: CalendarEventCreate, db: Session = Depends(get_db)):
    """创建运营日历事件"""
    new_event = OperationCalendar(
        event_date=event.event_date,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        product_id=event.product_id,
        product_name=event.product_name,
        operator=event.operator,
        tags=event.tags,
        budget=event.budget or 0,
        status=event.status or "planned",
        priority=event.priority or "medium",
        repeat_type=event.repeat_type,
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    return ResponseModel(data={"id": new_event.id, "message": "事件创建成功"})

@router.put("/events/{event_id}", response_model=ResponseModel)
def update_calendar_event(event_id: int, update_data: CalendarEventUpdate, db: Session = Depends(get_db)):
    """更新运营日历事件"""
    event = db.query(OperationCalendar).filter(OperationCalendar.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(event, field, value)
    
    db.commit()
    return ResponseModel(data={"message": "事件更新成功"})

@router.delete("/events/{event_id}", response_model=ResponseModel)
def delete_calendar_event(event_id: int, db: Session = Depends(get_db)):
    """删除运营日历事件"""
    event = db.query(OperationCalendar).filter(OperationCalendar.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    db.delete(event)
    db.commit()
    return ResponseModel(data={"message": "事件删除成功"})

@router.get("/types", response_model=ResponseModel)
def get_event_types(db: Session = Depends(get_db)):
    """获取所有事件类型"""
    types = db.query(
        OperationCalendar.event_type,
        func.count(OperationCalendar.id).label("count"),
    ).group_by(OperationCalendar.event_type).all()
    
    return ResponseModel(data={
        "types": [{"type": t.event_type, "count": t.count} for t in types],
    })

@router.get("/effectiveness", response_model=ResponseModel)
def get_effectiveness_analysis(
    event_type: Optional[str] = Query(None, description="事件类型"),
    db: Session = Depends(get_db)
):
    """分析运营动作效果"""
    query = db.query(OperationCalendar).filter(
        OperationCalendar.effectiveness_score > 0,
    )
    if event_type:
        query = query.filter(OperationCalendar.event_type == event_type)
    
    events = query.all()
    
    by_type = {}
    for e in events:
        if e.event_type not in by_type:
            by_type[e.event_type] = {"count": 0, "total_score": 0, "avg_roi": 0, "roi_count": 0}
        by_type[e.event_type]["count"] += 1
        by_type[e.event_type]["total_score"] += e.effectiveness_score or 0
        if e.roi and e.roi > 0:
            by_type[e.event_type]["avg_roi"] += e.roi
            by_type[e.event_type]["roi_count"] += 1
    
    for t in by_type:
        by_type[t]["avg_score"] = round(by_type[t]["total_score"] / max(by_type[t]["count"], 1), 1)
        by_type[t]["avg_roi"] = round(by_type[t]["avg_roi"] / max(by_type[t]["roi_count"], 1), 2)
    
    return ResponseModel(data={
        "analysis": by_type,
        "total_events": len(events),
    })
