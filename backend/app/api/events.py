"""
图表事件标记 API
实现运营动作在趋势图上的事件标记线功能
"""
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.core.logger import get_logger
from app.models import OperationAction, WeeklyData, DailyData, MonthlyData, Product
from app.schemas.common import ResponseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/events", tags=["图表事件"])


ACTION_CATEGORIES = {
    "price_change": {"label": "调价", "color": "#E6A23C", "icon": "price-tag"},
    "ad_adjust": {"label": "调推广", "color": "#409EFF", "icon": "promotion"},
    "image_change": {"label": "换图", "color": "#67C23A", "icon": "picture"},
    "title_change": {"label": "改标题", "color": "#909399", "icon": "edit"},
    "stock_change": {"label": "库存调整", "color": "#F56C6C", "icon": "box"},
    "promotion": {"label": "活动", "color": "#9B59B6", "icon": "calendar"},
    "other": {"label": "其他", "color": "#95A5A6", "icon": "more"}
}


@router.get("/list", response_model=ResponseModel)
def get_events(
    product_id: Optional[str] = Query(None, description="商品ID筛选"),
    action_type: Optional[str] = Query(None, description="动作类型筛选"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取事件列表"""
    
    query = db.query(OperationAction)
    
    if product_id:
        query = query.filter(OperationAction.product_id == product_id)
    
    if action_type:
        query = query.filter(OperationAction.action_type == action_type)
    
    if start_date:
        query = query.filter(OperationAction.action_date >= start_date)
    
    if end_date:
        query = query.filter(OperationAction.action_date <= end_date)
    
    events = query.order_by(desc(OperationAction.action_date)).limit(limit).all()
    
    result = []
    for e in events:
        category = ACTION_CATEGORIES.get(e.action_type, ACTION_CATEGORIES["other"])
        
        product = db.query(Product).filter(Product.product_id == e.product_id).first()
        
        result.append({
            "id": e.id,
            "product_id": e.product_id,
            "product_name": product.title if product else "",
            "action_date": e.action_date.isoformat() if hasattr(e.action_date, 'isoformat') else str(e.action_date),
            "action_type": e.action_type,
            "action_detail": e.action_detail,
            "category_label": category["label"],
            "color": category["color"],
            "icon": category["icon"],
            "effect_score": e.effect_score,
            "before_data": {
                "gmv": e.before_gmv,
                "visitors": e.before_visitors,
                "conversion": e.before_conversion,
                "roi": e.before_roi
            } if e.before_gmv else None,
            "after_data": {
                "gmv": e.after_gmv,
                "visitors": e.after_visitors,
                "conversion": e.after_conversion,
                "roi": e.after_roi
            } if e.after_gmv else None,
            "created_at": e.created_at.isoformat() if e.created_at else None
        })
    
    return ResponseModel(data={
        "events": result,
        "categories": ACTION_CATEGORIES
    })


@router.get("/chart-markers", response_model=ResponseModel)
def get_chart_markers(
    product_id: Optional[str] = Query(None, description="商品ID"),
    dimension: str = Query("weekly", description="时间维度"),
    start_period: Optional[str] = Query(None, description="开始周期"),
    end_period: Optional[str] = Query(None, description="结束周期"),
    db: Session = Depends(get_db)
):
    """获取图表标记线数据 - 用于在趋势图上显示事件"""
    
    query = db.query(OperationAction)
    
    if product_id:
        query = query.filter(OperationAction.product_id == product_id)
    
    if start_period:
        query = query.filter(OperationAction.action_date >= start_period)
    
    if end_period:
        query = query.filter(OperationAction.action_date <= end_period)
    
    events = query.order_by(OperationAction.action_date).all()
    
    markers = []
    for e in events:
        category = ACTION_CATEGORIES.get(e.action_type, ACTION_CATEGORIES["other"])
        
        period = e.action_date.isoformat() if hasattr(e.action_date, 'isoformat') else str(e.action_date)
        
        if dimension == "weekly":
            week_start = e.action_date - timedelta(days=e.action_date.weekday())
            period = week_start.strftime("%Y-%m-%d")
        elif dimension == "monthly":
            period = e.action_date.strftime("%Y-%m")
        
        marker = {
            "period": period,
            "name": category["label"],
            "label": {
                "show": True,
                "formatter": category["label"],
                "position": "end"
            },
            "lineStyle": {
                "color": category["color"],
                "type": "dashed",
                "width": 2
            },
            "event_id": e.id,
            "action_type": e.action_type,
            "action_detail": e.action_detail,
            "effect_score": e.effect_score
        }
        
        if e.effect_score:
            if e.effect_score >= 7:
                marker["label"]["color"] = "#67C23A"
            elif e.effect_score >= 4:
                marker["label"]["color"] = "#E6A23C"
            else:
                marker["label"]["color"] = "#F56C6C"
        
        markers.append(marker)
    
    return ResponseModel(data={
        "dimension": dimension,
        "markers": markers,
        "categories": ACTION_CATEGORIES
    })


@router.get("/product/{product_id}/timeline", response_model=ResponseModel)
def get_product_timeline(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度"),
    periods: int = Query(12, description="周期数"),
    db: Session = Depends(get_db)
):
    """获取商品运营时间线 - 数据趋势 + 事件标记"""
    
    from app.core.utils import get_data_model
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    data_points = db.query(Model).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(periods).all()
    
    events = db.query(OperationAction).filter(
        OperationAction.product_id == product_id
    ).order_by(OperationAction.action_date).all()
    
    timeline = []
    
    for dp in reversed(data_points):
        period = getattr(dp, date_col)
        if hasattr(period, 'isoformat'):
            period_str = period.isoformat()
        else:
            period_str = str(period)
        
        event_markers = []
        for e in events:
            event_period = e.action_date.isoformat() if hasattr(e.action_date, 'isoformat') else str(e.action_date)
            
            if dimension == "weekly":
                from datetime import timedelta
                week_start = e.action_date - timedelta(days=e.action_date.weekday())
                event_period = week_start.strftime("%Y-%m-%d")
            elif dimension == "monthly":
                event_period = e.action_date.strftime("%Y-%m")
            
            if event_period == period_str:
                category = ACTION_CATEGORIES.get(e.action_type, ACTION_CATEGORIES["other"])
                event_markers.append({
                    "action_type": e.action_type,
                    "label": category["label"],
                    "color": category["color"],
                    "detail": e.action_detail,
                    "effect_score": e.effect_score
                })
        
        timeline.append({
            "period": period_str,
            "gmv": float(dp.payment_amount or 0),
            "visitors": int(getattr(dp, visitors_col) or 0),
            "conversion": float(dp.payment_conversion or 0) * 100,
            "roi": float(dp.ad_roi or 0) if dp.ad_roi else 0,
            "events": event_markers
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "dimension": dimension,
        "timeline": timeline
    })


@router.post("/analyze-effect", response_model=ResponseModel)
def analyze_event_effect(
    event_id: int = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """分析事件效果 - 前后数据对比"""
    
    event = db.query(OperationAction).filter(OperationAction.id == event_id).first()
    
    if not event:
        return ResponseModel(data={"error": "事件不存在"})
    
    analysis = {
        "event_id": event_id,
        "action_type": event.action_type,
        "action_detail": event.action_detail,
        "action_date": event.action_date.isoformat() if hasattr(event.action_date, 'isoformat') else str(event.action_date),
        "before": {
            "gmv": event.before_gmv,
            "visitors": event.before_visitors,
            "conversion": event.before_conversion,
            "roi": event.before_roi
        },
        "after": {
            "gmv": event.after_gmv,
            "visitors": event.after_visitors,
            "conversion": event.after_conversion,
            "roi": event.after_roi
        },
        "changes": {}
    }
    
    if event.before_gmv and event.after_gmv:
        analysis["changes"]["gmv_change"] = event.after_gmv - event.before_gmv
        analysis["changes"]["gmv_change_pct"] = round(
            (event.after_gmv - event.before_gmv) / event.before_gmv * 100, 1
        ) if event.before_gmv > 0 else 0
    
    if event.before_visitors and event.after_visitors:
        analysis["changes"]["visitors_change"] = event.after_visitors - event.before_visitors
        analysis["changes"]["visitors_change_pct"] = round(
            (event.after_visitors - event.before_visitors) / event.before_visitors * 100, 1
        ) if event.before_visitors > 0 else 0
    
    if event.before_conversion and event.after_conversion:
        analysis["changes"]["conversion_change"] = round(
            (event.after_conversion - event.before_conversion) * 100, 2
        )
    
    if event.before_roi and event.after_roi:
        analysis["changes"]["roi_change"] = round(event.after_roi - event.before_roi, 2)
    
    analysis["effect_score"] = event.effect_score
    analysis["effect_level"] = "positive" if event.effect_score and event.effect_score >= 5 else "negative"
    
    return ResponseModel(data=analysis)


@router.get("/categories", response_model=ResponseModel)
def get_action_categories():
    """获取动作类型列表"""
    return ResponseModel(data={
        "categories": [
            {"value": k, "label": v["label"], "color": v["color"], "icon": v["icon"]}
            for k, v in ACTION_CATEGORIES.items()
        ]
    })


from datetime import timedelta
