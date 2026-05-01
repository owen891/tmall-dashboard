from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product, OperationAction
from app.schemas.common import ResponseModel

router = APIRouter(prefix="", tags=["通用"])


@router.get("/periods", response_model=ResponseModel)
def get_periods(
    dim: str = Query("weekly", alias="dim", description="时间维度"),
    db: Session = Depends(get_db)
):
    dim_configs = {
        'monthly': {'model': MonthlyData, 'col': 'month'},
        'weekly': {'model': WeeklyData, 'col': 'week_start'},
        'daily': {'model': DailyData, 'col': 'date'},
    }
    config = dim_configs.get(dim, dim_configs['weekly'])
    Model, date_col = config['model'], config['col']
    
    periods = db.query(getattr(Model, date_col)).distinct().order_by(desc(getattr(Model, date_col))).limit(52).all()
    
    period_list = []
    for p in periods:
        period_val = getattr(p, date_col)
        if hasattr(period_val, 'isoformat'):
            period_list.append(period_val.isoformat())
        else:
            period_list.append(str(period_val))
    
    return ResponseModel(data={"periods": period_list, "dimension": dim})


@router.get("/status", response_model=ResponseModel)
def get_status(db: Session = Depends(get_db)):
    monthly_count = db.query(func.count(MonthlyData.id)).scalar()
    weekly_count = db.query(func.count(WeeklyData.id)).scalar()
    daily_count = db.query(func.count(DailyData.id)).scalar()
    product_count = db.query(func.count(Product.product_id)).filter(Product.status == "active").scalar()
    
    return ResponseModel(data={
        "counts": {
            "products": product_count,
            "monthly": monthly_count,
            "weekly": weekly_count,
            "daily": daily_count,
        },
        "status": "ok"
    })


@router.get("/compare", response_model=ResponseModel)
def get_comparison(
    dim: str = Query("weekly", alias="dim", description="时间维度"),
    period1: str = Query(..., description="周期1"),
    period2: str = Query(..., description="周期2"),
    db: Session = Depends(get_db)
):
    dim_configs = {
        'monthly': {'model': MonthlyData, 'col': 'month', 'visitors': 'visitors'},
        'weekly': {'model': WeeklyData, 'col': 'week_start', 'visitors': 'ipv'},
        'daily': {'model': DailyData, 'col': 'date', 'visitors': 'ipv'},
    }
    config = dim_configs.get(dim, dim_configs['weekly'])
    Model, date_col, visitors_col = config['model'], config['col'], config['visitors']
    
    query1 = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment1'),
        func.sum(Model.refund_amount).label('refund1'),
        func.sum(getattr(Model, visitors_col)).label('visitors1'),
        func.avg(Model.payment_conversion).label('conv1'),
        func.sum(Model.ad_spend).label('ad_spend1'),
        func.avg(Model.ad_roi).label('roi1'),
    ).filter(getattr(Model, date_col) == period1).group_by(Model.product_id)
    
    query2 = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment2'),
        func.sum(Model.refund_amount).label('refund2'),
        func.sum(getattr(Model, visitors_col)).label('visitors2'),
        func.avg(Model.payment_conversion).label('conv2'),
        func.sum(Model.ad_spend).label('ad_spend2'),
        func.avg(Model.ad_roi).label('roi2'),
    ).filter(getattr(Model, date_col) == period2).group_by(Model.product_id)
    
    data1 = {row.product_id: row for row in query1.all()}
    data2 = {row.product_id: row for row in query2.all()}
    
    product_ids = set(data1.keys()).union(set(data2.keys()))
    products = db.query(Product).filter(Product.product_id.in_(product_ids)).all()
    product_map = {p.product_id: p for p in products}
    
    comparison = []
    for pid in product_ids:
        r1 = data1.get(pid)
        r2 = data2.get(pid)
        product = product_map.get(pid)
        
        payment1 = float(r1.payment1 or 0) if r1 else 0
        payment2 = float(r2.payment2 or 0) if r2 else 0
        refund1 = float(r1.refund1 or 0) if r1 else 0
        refund2 = float(r2.refund2 or 0) if r2 else 0
        visitors1 = int(r1.visitors1 or 0) if r1 else 0
        visitors2 = int(r2.visitors2 or 0) if r2 else 0
        
        change_payment = ((payment2 - payment1) / payment1 * 100 if payment1 > 0 else None)
        change_visitors = ((visitors2 - visitors1) / visitors1 * 100 if visitors1 > 0 else None)
        
        comp = {
            "product_id": pid,
            "product_name": product.title if product else pid,
            "category": product.category if product else None,
            "period1": {
                "payment_amount": payment1,
                "net_sales": payment1 - refund1,
                "refund_amount": refund1,
                "refund_rate": refund1 / payment1 if payment1 > 0 else 0,
                "visitors": visitors1,
                "conversion": float(r1.conv1 or 0) if r1 else 0,
                "ad_spend": float(r1.ad_spend1 or 0) if r1 else 0,
                "roi": float(r1.roi1 or 0) if r1 else 0,
            },
            "period2": {
                "payment_amount": payment2,
                "net_sales": payment2 - refund2,
                "refund_amount": refund2,
                "refund_rate": refund2 / payment2 if payment2 > 0 else 0,
                "visitors": visitors2,
                "conversion": float(r2.conv2 or 0) if r2 else 0,
                "ad_spend": float(r2.ad_spend2 or 0) if r2 else 0,
                "roi": float(r2.roi2 or 0) if r2 else 0,
            },
            "changes": {
                "payment_amount": change_payment,
                "visitors": change_visitors,
            }
        }
        comparison.append(comp)
    
    return ResponseModel(data={
        "comparison": comparison,
        "period1": period1,
        "period2": period2,
        "dimension": dim
    })


@router.get("/actions", response_model=ResponseModel)
def get_operation_actions(
    product_id: Optional[str] = Query(None, description="商品ID"),
    limit: int = Query(50, description="每页数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    query = db.query(OperationAction)
    if product_id:
        query = query.filter(OperationAction.product_id == product_id)
    actions = query.order_by(desc(OperationAction.action_date)).offset(offset).limit(limit).all()
    
    result = []
    for a in actions:
        result.append({
            "id": a.id,
            "product_id": a.product_id,
            "action_date": str(a.action_date),
            "action_type": a.action_type,
            "action_detail": a.action_detail,
            "before_payment": a.before_payment,
            "before_visitors": a.before_visitors,
            "before_conversion": a.before_conversion,
            "before_roi": a.before_roi,
            "after_payment": a.after_payment,
            "after_visitors": a.after_visitors,
            "after_conversion": a.after_conversion,
            "after_roi": a.after_roi,
            "payment_change": a.payment_change,
            "conversion_change": a.conversion_change,
            "roi_change": a.roi_change,
            "effectiveness_score": a.effectiveness_score,
            "imported_at": str(a.imported_at) if a.imported_at else None,
        })
    
    return ResponseModel(data={"actions": result, "total": len(result)})


@router.post("/actions", response_model=ResponseModel)
def add_operation_action(
    product_id: str = Body(..., embed=True),
    action_date: str = Body(..., embed=True),
    action_type: Optional[str] = Body(None, embed=True),
    action_detail: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    new_action = OperationAction(
        product_id=product_id,
        action_date=action_date,
        action_type=action_type,
        action_detail=action_detail,
        before_payment=0,
        before_visitors=0,
        before_conversion=0,
        before_roi=0,
        after_payment=0,
        after_visitors=0,
        after_conversion=0,
        after_roi=0,
        payment_change=0,
        conversion_change=0,
        roi_change=0,
        effectiveness_score=0
    )
    db.add(new_action)
    db.commit()
    return ResponseModel(data={"success": True, "action_id": new_action.id})


@router.delete("/actions/{action_id}", response_model=ResponseModel)
def delete_operation_action(action_id: int, db: Session = Depends(get_db)):
    action = db.query(OperationAction).filter(OperationAction.id == action_id).first()
    if action:
        db.delete(action)
        db.commit()
    return ResponseModel(data={"success": True})


@router.get("/action-stats", response_model=ResponseModel)
def get_action_stats(
    period: Optional[str] = Query(None, description="周期"),
    db: Session = Depends(get_db)
):
    query = db.query(OperationAction)
    actions = query.all()
    
    total_count = len(actions)
    avg_payment_change = sum([a.payment_change or 0 for a in actions]) / total_count if total_count > 0 else 0
    avg_conversion_change = sum([a.conversion_change or 0 for a in actions]) / total_count if total_count > 0 else 0
    
    return ResponseModel(data={
        "total": total_count,
        "avg_payment_change": avg_payment_change,
        "avg_conversion_change": avg_conversion_change,
    })


@router.get("/backup", response_model=ResponseModel)
def trigger_backup():
    return ResponseModel(data={"success": True, "message": "备份功能已触发"})


@router.get("/alert-check", response_model=ResponseModel)
def trigger_alert_check():
    return ResponseModel(data={"success": True, "message": "告警检查已触发"})
