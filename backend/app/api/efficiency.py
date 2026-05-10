from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
from typing import Optional, List
from app.core.database import get_db
from app.models.command_tower import (
    UserKPI, TaskItem, CampaignProject, UserDailyPerformance
)
from app.models.operations import OperationAction
from app.schemas.common import ResponseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/efficiency", tags=["人效度量"])


@router.get("/overview", response_model=ResponseModel)
def get_efficiency_overview(
    db: Session = Depends(get_db)
):
    total_users = db.query(func.count(func.distinct(UserKPI.username))).scalar() or 0
    total_tasks = db.query(func.count(TaskItem.id)).scalar() or 0
    completed_tasks = db.query(func.count(TaskItem.id)).filter(TaskItem.status == 'completed').scalar() or 0
    avg_progress = db.query(func.avg(UserKPI.gmv_progress)).scalar() or 0

    return ResponseModel(data={
        "total_users": total_users,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
        "avg_progress": round(float(avg_progress), 2),
        "active_projects": db.query(func.count(func.distinct(CampaignProject.id))).scalar() or 0
    })


@router.get("/channels", response_model=ResponseModel)
def get_efficiency_channels(
    db: Session = Depends(get_db)
):
    return ResponseModel(data={"channels": []})


@router.get("/products", response_model=ResponseModel)
def get_efficiency_products(
    db: Session = Depends(get_db)
):
    return ResponseModel(data={"products": []})


@router.get("/users", response_model=ResponseModel)
def get_user_list(
    db: Session = Depends(get_db)
):
    """获取有KPI记录的用户列表"""
    users = db.query(UserKPI.username).distinct().all()
    user_list = [u[0] for u in users]
    return ResponseModel(data={"users": user_list})


@router.get("/user-kpis", response_model=ResponseModel)
def get_user_kpis(
    username: Optional[str] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取用户KPI列表"""
    query = db.query(UserKPI)
    if username:
        query = query.filter(UserKPI.username == username)
    if period:
        query = query.filter(UserKPI.period == period)
    
    kpis = query.order_by(desc(UserKPI.period)).all()
    
    result = []
    for kpi in kpis:
        result.append({
            "id": kpi.id,
            "username": kpi.username,
            "period": kpi.period,
            "target_gmv": kpi.target_gmv,
            "actual_gmv": kpi.actual_gmv,
            "gmv_progress": kpi.gmv_progress,
            "target_roi": kpi.target_roi,
            "actual_roi": kpi.actual_roi,
            "roi_progress": kpi.roi_progress,
            "target_task_count": kpi.target_task_count,
            "actual_task_count": kpi.actual_task_count,
            "task_progress": kpi.task_progress,
            "target_operation_count": kpi.target_operation_count,
            "actual_operation_count": kpi.actual_operation_count,
            "operation_progress": kpi.operation_progress,
            "performance_rating": kpi.performance_rating
        })
    
    return ResponseModel(data={"kpis": result})


@router.post("/user-kpis", response_model=ResponseModel)
def create_user_kpi(
    username: str,
    period: str,
    target_gmv: float = 0,
    target_roi: float = 0,
    target_task_count: int = 0,
    target_operation_count: int = 0,
    responsibility_description: str = "",
    db: Session = Depends(get_db)
):
    """创建用户KPI"""
    existing = db.query(UserKPI).filter(
        and_(UserKPI.username == username, UserKPI.period == period)
    ).first()
    
    if existing:
        existing.target_gmv = target_gmv
        existing.target_roi = target_roi
        existing.target_task_count = target_task_count
        existing.target_operation_count = target_operation_count
        existing.responsibility_description = responsibility_description
    else:
        kpi = UserKPI(
            username=username,
            period=period,
            target_gmv=target_gmv,
            target_roi=target_roi,
            target_task_count=target_task_count,
            target_operation_count=target_operation_count,
            responsibility_description=responsibility_description
        )
        db.add(kpi)
    
    db.commit()
    return ResponseModel(data={"message": "KPI创建/更新成功"})


@router.get("/dashboard", response_model=ResponseModel)
def get_efficiency_dashboard(
    username: Optional[str] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """人效总览看板"""
    # 默认取本月
    if not period:
        period = datetime.now().strftime("%Y-%m")
    
    query = db.query(UserKPI).filter(UserKPI.period == period)
    if username:
        query = query.filter(UserKPI.username == username)
    
    kpis = query.all()
    
    # 团队汇总
    total_target_gmv = sum(k.target_gmv for k in kpis)
    total_actual_gmv = sum(k.actual_gmv for k in kpis)
    avg_task_progress = sum(k.task_progress for k in kpis) / len(kpis) if kpis else 0
    
    # 个人排行
    user_rankings = []
    for kpi in kpis:
        user_rankings.append({
            "username": kpi.username,
            "actual_gmv": kpi.actual_gmv,
            "gmv_progress": kpi.gmv_progress,
            "task_progress": kpi.task_progress,
            "operation_progress": kpi.operation_progress,
            "performance_rating": kpi.performance_rating
        })
    user_rankings = sorted(user_rankings, key=lambda x: x["actual_gmv"], reverse=True)
    
    return ResponseModel(data={
        "team_summary": {
            "period": period,
            "user_count": len(kpis),
            "total_target_gmv": total_target_gmv,
            "total_actual_gmv": total_actual_gmv,
            "total_progress": (total_actual_gmv / total_target_gmv * 100) if total_target_gmv > 0 else 0,
            "avg_task_progress": avg_task_progress
        },
        "user_rankings": user_rankings
    })


@router.get("/tasks", response_model=ResponseModel)
def get_tasks(
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    query = db.query(TaskItem)
    if assignee:
        query = query.filter(TaskItem.assignee == assignee)
    if status:
        query = query.filter(TaskItem.status == status)
    if project_id:
        query = query.filter(TaskItem.project_id == project_id)
    
    total = query.count()
    tasks = query.order_by(desc(TaskItem.created_at)).offset(offset).limit(limit).all()
    
    result = []
    for task in tasks:
        project = db.query(CampaignProject).filter(CampaignProject.id == task.project_id).first()
        result.append({
            "id": task.id,
            "task_title": task.task_title,
            "task_type": task.task_type,
            "description": task.description,
            "project_id": task.project_id,
            "project_name": project.project_name if project else None,
            "assignee": task.assignee,
            "reporter": task.reporter,
            "priority": task.priority,
            "status": task.status,
            "due_date": task.due_date,
            "start_date": task.start_date,
            "actual_date": task.actual_date,
            "deliverable": task.deliverable,
            "created_at": task.created_at.isoformat() if task.created_at else None
        })
    
    return ResponseModel(data={"tasks": result, "total": total})


@router.post("/tasks", response_model=ResponseModel)
def create_task(
    task_title: str,
    task_type: str = "general",
    assignee: str = "",
    reporter: str = "",
    priority: str = "medium",
    due_date: str = "",
    description: str = "",
    project_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """创建任务"""
    task = TaskItem(
        task_title=task_title,
        task_type=task_type,
        assignee=assignee,
        reporter=reporter,
        priority=priority,
        due_date=due_date,
        description=description,
        project_id=project_id,
        status="todo"
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return ResponseModel(data={"id": task.id, "message": "任务创建成功"})


@router.put("/tasks/{task_id}", response_model=ResponseModel)
def update_task_status(
    task_id: int,
    status: str = "todo",
    action_taken: str = "",
    result: str = "",
    db: Session = Depends(get_db)
):
    """更新任务状态"""
    task = db.query(TaskItem).filter(TaskItem.id == task_id).first()
    if not task:
        return ResponseModel(code=404, message="任务不存在")
    
    task.status = status
    if status == "done":
        task.actual_date = datetime.now().strftime("%Y-%m-%d")
    if action_taken:
        task.result = (task.result or "") + "\n" + action_taken
    if result:
        task.result = result
    
    task.updated_at = datetime.now()
    db.commit()
    
    return ResponseModel(data={"message": "任务更新成功"})


@router.get("/user-timeline", response_model=ResponseModel)
def get_user_timeline(
    username: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取用户时间线（任务+动作）"""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    # 获取任务
    tasks = db.query(TaskItem).filter(
        and_(TaskItem.assignee == username,
            TaskItem.created_at >= start_date,
            TaskItem.created_at <= end_date)
    ).all()
    
    # 获取动作
    operations = db.query(OperationAction).filter(
        OperationAction.created_at >= start_date
    ).all()
    
    # 合并时间线
    timeline_items = []
    for task in tasks:
        timeline_items.append({
            "type": "task",
            "title": task.task_title,
            "status": task.status,
            "date": task.created_at.isoformat() if task.created_at else None,
            "description": task.description
        })
    
    for op in operations:
        timeline_items.append({
            "type": "operation",
            "title": op.action_type or "运营动作",
            "product_id": op.product_id,
            "date": op.action_date,
            "description": op.action_detail,
            "effectiveness": op.effectiveness_score
        })
    
    # 按时间排序
    timeline_items = sorted(timeline_items, key=lambda x: x["date"], reverse=True)
    
    return ResponseModel(data={"timeline": timeline_items[:100]})


@router.get("/kanban", response_model=ResponseModel)
def get_kanban_board(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取看板视图"""
    query = db.query(TaskItem)
    if project_id:
        query = query.filter(TaskItem.project_id == project_id)
    
    tasks = query.all()
    
    kanban = {
        "todo": [],
        "in_progress": [],
        "blocked": [],
        "done": []
    }
    
    for task in tasks:
        status = task.status if task.status in kanban else "todo"
        kanban[status].append({
            "id": task.id,
            "task_title": task.task_title,
            "assignee": task.assignee,
            "priority": task.priority,
            "due_date": task.due_date
        })
    
    return ResponseModel(data={"kanban": kanban})

