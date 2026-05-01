from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, ChartEvent
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/trends", tags=["趋势分析"])


@router.get("/product/{product_id}", response_model=ResponseModel)
def get_product_trend(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    metrics: Optional[str] = Query(None, description="指标列表，逗号分隔，如: gmv,visitors,conversion"),
    periods: int = Query(12, description="返回周期数"),
    db: Session = Depends(get_db)
):
    """获取商品趋势数据（多指标）"""
    
    default_metrics = ["gmv", "visitors", "conversion", "roi"]
    metric_list = metrics.split(",") if metrics else default_metrics
    
    if dimension == "daily":
        data_list = db.query(DailyData).filter(
            DailyData.product_id == product_id
        ).order_by(desc(DailyData.date)).limit(periods).all()
        
        result = []
        for data in reversed(data_list):
            item = {"period": data.date.isoformat()}
            if "gmv" in metric_list:
                item["gmv"] = data.payment_amount
            if "visitors" in metric_list:
                item["visitors"] = data.ipv
            if "conversion" in metric_list:
                item["conversion"] = data.payment_conversion
            if "roi" in metric_list:
                item["roi"] = data.ad_roi
            if "ad_spend" in metric_list:
                item["ad_spend"] = data.ad_spend
            if "uv_value" in metric_list:
                item["uv_value"] = data.payment_amount / data.ipv if data.ipv > 0 else 0
            if "net_sales" in metric_list:
                item["net_sales"] = data.net_sales
            result.append(item)
    
    elif dimension == "monthly":
        data_list = db.query(MonthlyData).filter(
            MonthlyData.product_id == product_id
        ).order_by(desc(MonthlyData.month)).limit(periods).all()
        
        result = []
        for data in reversed(data_list):
            item = {"period": data.month}
            if "gmv" in metric_list:
                item["gmv"] = data.payment_amount
            if "visitors" in metric_list:
                item["visitors"] = data.visitors
            if "conversion" in metric_list:
                item["conversion"] = data.payment_conversion
            if "roi" in metric_list:
                item["roi"] = data.ad_roi
            if "ad_spend" in metric_list:
                item["ad_spend"] = data.ad_spend
            if "uv_value" in metric_list:
                item["uv_value"] = data.uv_value
            if "net_sales" in metric_list:
                item["net_sales"] = data.net_sales
            if "keyword_spend" in metric_list:
                item["keyword_spend"] = data.keyword_spend
            if "keyword_roi" in metric_list:
                item["keyword_roi"] = data.keyword_roi
            if "crowd_spend" in metric_list:
                item["crowd_spend"] = data.crowd_spend
            if "crowd_roi" in metric_list:
                item["crowd_roi"] = data.crowd_roi
            result.append(item)
    
    else:
        dimension = "weekly"
        data_list = db.query(WeeklyData).filter(
            WeeklyData.product_id == product_id
        ).order_by(desc(WeeklyData.week_start)).limit(periods).all()
        
        result = []
        for data in reversed(data_list):
            item = {"period": data.week_start.isoformat()}
            if "gmv" in metric_list:
                item["gmv"] = data.payment_amount
            if "visitors" in metric_list:
                item["visitors"] = data.ipv
            if "conversion" in metric_list:
                item["conversion"] = data.payment_conversion
            if "roi" in metric_list:
                item["roi"] = data.ad_roi
            if "ad_spend" in metric_list:
                item["ad_spend"] = data.ad_spend
            if "net_sales" in metric_list:
                item["net_sales"] = data.net_sales
            if "cart_rate" in metric_list:
                item["cart_rate"] = data.cart_rate
            if "fav_rate" in metric_list:
                item["fav_rate"] = data.fav_rate
            result.append(item)
    
    events = db.query(ChartEvent).filter(
        ChartEvent.product_id == product_id,
        ChartEvent.chart_type == dimension
    ).order_by(ChartEvent.event_date).all()
    
    event_markers = [
        {
            "period": e.event_date.isoformat() if hasattr(e.event_date, 'isoformat') else str(e.event_date),
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description
        }
        for e in events
    ]
    
    return ResponseModel(data={
        "product_id": product_id,
        "dimension": dimension,
        "metrics": metric_list,
        "trend": result,
        "events": event_markers,
        "count": len(result)
    })


@router.get("/shop", response_model=ResponseModel)
def get_shop_trend(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    metrics: Optional[str] = Query(None, description="指标列表"),
    periods: int = Query(12, description="返回周期数"),
    db: Session = Depends(get_db)
):
    """获取店铺整体趋势"""
    
    default_metrics = ["gmv", "visitors", "conversion", "roi", "ad_spend"]
    metric_list = metrics.split(",") if metrics else default_metrics
    
    if dimension == "daily":
        query = db.query(
            DailyData.date,
            func.sum(DailyData.payment_amount).label('gmv'),
            func.sum(DailyData.ipv).label('visitors'),
            func.avg(DailyData.payment_conversion).label('conversion'),
            func.avg(DailyData.ad_roi).label('roi'),
            func.sum(DailyData.ad_spend).label('ad_spend'),
            func.sum(DailyData.net_sales).label('net_sales')
        ).group_by(DailyData.date).order_by(desc(DailyData.date)).limit(periods).all()
        
        result = []
        for row in reversed(query):
            item = {"period": row.date.isoformat()}
            if "gmv" in metric_list:
                item["gmv"] = float(row.gmv or 0)
            if "visitors" in metric_list:
                item["visitors"] = int(row.visitors or 0)
            if "conversion" in metric_list:
                item["conversion"] = float(row.conversion or 0)
            if "roi" in metric_list:
                item["roi"] = float(row.roi or 0)
            if "ad_spend" in metric_list:
                item["ad_spend"] = float(row.ad_spend or 0)
            if "net_sales" in metric_list:
                item["net_sales"] = float(row.net_sales or 0)
            result.append(item)
    
    elif dimension == "monthly":
        query = db.query(
            MonthlyData.month,
            func.sum(MonthlyData.payment_amount).label('gmv'),
            func.sum(MonthlyData.visitors).label('visitors'),
            func.avg(MonthlyData.payment_conversion).label('conversion'),
            func.avg(MonthlyData.ad_roi).label('roi'),
            func.sum(MonthlyData.ad_spend).label('ad_spend'),
            func.sum(MonthlyData.net_sales).label('net_sales')
        ).group_by(MonthlyData.month).order_by(desc(MonthlyData.month)).limit(periods).all()
        
        result = []
        for row in reversed(query):
            item = {"period": row.month}
            if "gmv" in metric_list:
                item["gmv"] = float(row.gmv or 0)
            if "visitors" in metric_list:
                item["visitors"] = int(row.visitors or 0)
            if "conversion" in metric_list:
                item["conversion"] = float(row.conversion or 0)
            if "roi" in metric_list:
                item["roi"] = float(row.roi or 0)
            if "ad_spend" in metric_list:
                item["ad_spend"] = float(row.ad_spend or 0)
            if "net_sales" in metric_list:
                item["net_sales"] = float(row.net_sales or 0)
            result.append(item)
    
    else:
        dimension = "weekly"
        query = db.query(
            WeeklyData.week_start,
            func.sum(WeeklyData.payment_amount).label('gmv'),
            func.sum(WeeklyData.ipv).label('visitors'),
            func.avg(WeeklyData.payment_conversion).label('conversion'),
            func.avg(WeeklyData.ad_roi).label('roi'),
            func.sum(WeeklyData.ad_spend).label('ad_spend'),
            func.sum(WeeklyData.net_sales).label('net_sales')
        ).group_by(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).limit(periods).all()
        
        result = []
        for row in reversed(query):
            item = {"period": row.week_start.isoformat()}
            if "gmv" in metric_list:
                item["gmv"] = float(row.gmv or 0)
            if "visitors" in metric_list:
                item["visitors"] = int(row.visitors or 0)
            if "conversion" in metric_list:
                item["conversion"] = float(row.conversion or 0)
            if "roi" in metric_list:
                item["roi"] = float(row.roi or 0)
            if "ad_spend" in metric_list:
                item["ad_spend"] = float(row.ad_spend or 0)
            if "net_sales" in metric_list:
                item["net_sales"] = float(row.net_sales or 0)
            result.append(item)
    
    return ResponseModel(data={
        "dimension": dimension,
        "metrics": metric_list,
        "trend": result,
        "count": len(result)
    })


@router.post("/events", response_model=ResponseModel)
def create_chart_event(
    product_id: Optional[str] = None,
    chart_type: str = "weekly",
    event_date: str = "",
    event_type: str = "operation",
    title: str = "",
    description: Optional[str] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """创建图表事件标记"""
    from datetime import datetime
    
    event = ChartEvent(
        product_id=product_id,
        chart_type=chart_type,
        event_date=datetime.strptime(event_date, "%Y-%m-%d").date() if event_date else datetime.now().date(),
        event_type=event_type,
        title=title,
        description=description,
        period=period
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    
    return ResponseModel(data={
        "message": "事件已创建",
        "event": {
            "id": event.id,
            "product_id": event.product_id,
            "chart_type": event.chart_type,
            "event_date": event.event_date.isoformat(),
            "event_type": event.event_type,
            "title": event.title,
            "description": event.description
        }
    })


@router.delete("/events/{event_id}", response_model=ResponseModel)
def delete_chart_event(event_id: int, db: Session = Depends(get_db)):
    """删除图表事件"""
    event = db.query(ChartEvent).filter(ChartEvent.id == event_id).first()
    if not event:
        return ResponseModel(data={"message": "事件不存在"})
    
    db.delete(event)
    db.commit()
    
    return ResponseModel(data={"message": "事件已删除"})


@router.get("/events", response_model=ResponseModel)
def get_chart_events(
    product_id: Optional[str] = None,
    chart_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取图表事件列表"""
    query = db.query(ChartEvent)
    
    if product_id:
        query = query.filter(ChartEvent.product_id == product_id)
    if chart_type:
        query = query.filter(ChartEvent.chart_type == chart_type)
    
    events = query.order_by(desc(ChartEvent.event_date)).all()
    
    return ResponseModel(data={
        "events": [
            {
                "id": e.id,
                "product_id": e.product_id,
                "chart_type": e.chart_type,
                "event_date": e.event_date.isoformat(),
                "event_type": e.event_type,
                "title": e.title,
                "description": e.description
            }
            for e in events
        ],
        "count": len(events)
    })
