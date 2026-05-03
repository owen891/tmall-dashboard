from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.core.database import get_db
from app.models.command_tower import TaskItem, UserKPI

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


class TaskCreate(BaseModel):
    task_title: str
    task_type: Optional[str] = None
    description: Optional[str] = None
    priority: str = "P2"
    assignee: Optional[str] = None
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    task_title: Optional[str] = None
    task_type: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None


@router.get("")
async def get_tasks(
    status: Optional[str] = Query(None, description="状态"),
    priority: Optional[str] = Query(None, description="优先级"),
    assignee: Optional[str] = Query(None, description="负责人"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """任务列表"""
    query = db.query(TaskItem)
    
    if status:
        query = query.filter(TaskItem.status == status)
    if priority:
        query = query.filter(TaskItem.priority == priority)
    if assignee:
        query = query.filter(TaskItem.assignee == assignee)
    
    tasks = query.order_by(
        TaskItem.status.asc(),
        TaskItem.priority.desc(),
        TaskItem.due_date.asc()
    ).limit(limit).all()
    
    return {
        "items": [
            {
                "task_id": t.id,
                "task_title": t.task_title,
                "task_type": t.task_type,
                "description": t.description,
                "priority": t.priority,
                "assignee": t.assignee,
                "due_date": t.due_date,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tasks
        ],
        "total": len(tasks)
    }


@router.post("")
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    """创建任务"""
    db_task = TaskItem(
        task_title=task.task_title,
        task_type=task.task_type,
        description=task.description,
        priority=task.priority,
        assignee=task.assignee,
        due_date=task.due_date,
        status="todo"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return {"task_id": db_task.id, "success": True}


@router.put("/{task_id}")
async def update_task(
    task_id: int,
    update: TaskUpdate,
    db: Session = Depends(get_db)
):
    """更新任务"""
    db_task = db.query(TaskItem).filter(TaskItem.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(db_task, field, value)
    
    db.commit()
    
    return {"success": True}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """删除任务"""
    db_task = db.query(TaskItem).filter(TaskItem.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.delete(db_task)
    db.commit()
    
    return {"success": True}


@router.get("/stats")
async def get_task_stats(
    db: Session = Depends(get_db)
):
    """任务统计"""
    total = db.query(func.count(TaskItem.id)).scalar() or 0
    todo = db.query(func.count(TaskItem.id)).filter(
        TaskItem.status == 'todo'
    ).scalar() or 0
    in_progress = db.query(func.count(TaskItem.id)).filter(
        TaskItem.status == 'in_progress'
    ).scalar() or 0
    done = db.query(func.count(TaskItem.id)).filter(
        TaskItem.status == 'done'
    ).scalar() or 0
    
    return {
        "total": total,
        "todo": todo,
        "in_progress": in_progress,
        "done": done
    }


router_kpi = APIRouter(prefix="/api/kpis", tags=["KPI管理"])


@router_kpi.get("")
async def get_kpis(
    period: Optional[str] = Query(None, description="周期"),
    db: Session = Depends(get_db)
):
    """KPI列表"""
    query = db.query(UserKPI)
    
    if period:
        query = query.filter(UserKPI.period == period)
    
    kpis = query.order_by(UserKPI.username).all()
    
    return {
        "items": [
            {
                "user_id": k.username,
                "user_name": k.username,
                "period": k.period,
                "target_gmv": k.target_gmv,
                "actual_gmv": k.actual_gmv,
                "achievement_rate": k.achievement_rate,
                "rating": k.rating,
                "target_task_count": k.target_task_count,
                "actual_task_count": k.actual_task_count
            }
            for k in kpis
        ],
        "total": len(kpis)
    }


@router_kpi.get("/stats")
async def get_kpi_stats(
    db: Session = Depends(get_db)
):
    """KPI统计"""
    total_users = db.query(func.count(func.distinct(UserKPI.username))).scalar() or 0
    
    avg_achievement = db.query(func.avg(UserKPI.achievement_rate)).scalar() or 0
    
    a_rated = db.query(func.count(UserKPI.id)).filter(
        UserKPI.rating == 'A'
    ).scalar() or 0
    b_rated = db.query(func.count(UserKPI.id)).filter(
        UserKPI.rating == 'B'
    ).scalar() or 0
    c_rated = db.query(func.count(UserKPI.id)).filter(
        UserKPI.rating == 'C'
    ).scalar() or 0
    
    return {
        "total_users": total_users,
        "avg_achievement": round(avg_achievement, 2),
        "a_rated": a_rated,
        "b_rated": b_rated,
        "c_rated": c_rated
    }
