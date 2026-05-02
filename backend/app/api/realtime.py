from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.core.database import get_db
from app.models import Product, WeeklyData, DailyData, Alert
import asyncio
import json
from datetime import datetime
import random

router = APIRouter(prefix="/realtime", tags=["实时数据"])


@router.get("/stream")
async def realtime_stream(db: Session = Depends(get_db)):
    """
    实时数据流 (SSE)
    推送关键指标变化
    """
    async def event_generator():
        while True:
            try:
                summary = get_realtime_summary(db)
                alert_count = db.query(Alert).filter(Alert.dismissed == False).count()
                
                data = {
                    "type": "update",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "summary": summary,
                        "alert_count": alert_count
                    }
                }
                
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                await asyncio.sleep(30)
                
            except Exception as e:
                error_data = {
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(60)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/summary")
def get_realtime_summary(db: Session = Depends(get_db)):
    """
    获取实时汇总数据
    """
    latest_week = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
    week_start = latest_week.week_start if latest_week else datetime.now().strftime("%Y-%m-%d")
    
    week_stats = db.query(
        func.sum(WeeklyData.payment_amount).label('gmv'),
        func.sum(WeeklyData.ipv).label('visitors'),
        func.avg(WeeklyData.payment_conversion).label('conversion'),
        func.sum(WeeklyData.ad_spend).label('ad_spend'),
        func.avg(WeeklyData.ad_roi).label('roi'),
    ).filter(WeeklyData.week_start == week_start).first()
    
    product_count = db.query(Product).filter(Product.status == 'active').count()
    
    return {
        "gmv": round(week_stats.gmv or 0, 2),
        "visitors": week_stats.visitors or 0,
        "conversion": round((week_stats.conversion or 0) * 100, 2),
        "ad_spend": round(week_stats.ad_spend or 0, 2),
        "roi": round(week_stats.roi or 0, 2),
        "product_count": product_count,
        "period": week_start
    }


@router.get("/top-products")
def get_realtime_top_products(limit: int = 5, db: Session = Depends(get_db)):
    """
    获取实时热销商品
    """
    latest_week = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
    week_start = latest_week.week_start if latest_week else datetime.now().strftime("%Y-%m-%d")
    
    results = db.query(Product, WeeklyData).join(
        WeeklyData, Product.product_id == WeeklyData.product_id
    ).filter(
        WeeklyData.week_start == week_start,
        Product.status == 'active'
    ).order_by(desc(WeeklyData.payment_amount)).limit(limit).all()
    
    products = []
    for i, (product, weekly) in enumerate(results):
        products.append({
            "rank": i + 1,
            "product_id": product.product_id,
            "title": product.title[:30] + "..." if len(product.title) > 30 else product.title,
            "gmv": round(weekly.payment_amount or 0, 2),
            "visitors": weekly.ipv or 0
        })
    
    return products


@router.get("/health-distribution")
def get_realtime_health(db: Session = Depends(get_db)):
    """
    获取实时健康度分布
    """
    total = db.query(Product).filter(Product.status == 'active').count()
    
    tiers = {}
    results = db.query(Product.tier, func.count(Product.id)).filter(
        Product.status == 'active',
        Product.tier.isnot(None)
    ).group_by(Product.tier).all()
    
    for tier, count in results:
        tiers[tier] = {
            "count": count,
            "percentage": round(count / total * 100, 1) if total > 0 else 0
        }
    
    return {
        "total": total,
        "by_tier": tiers
    }


def get_realtime_summary(db: Session):
    """内部函数：获取实时汇总"""
    latest_week = db.query(WeeklyData.week_start).order_by(desc(WeeklyData.week_start)).first()
    week_start = latest_week.week_start if latest_week else datetime.now().strftime("%Y-%m-%d")
    
    week_stats = db.query(
        func.sum(WeeklyData.payment_amount).label('gmv'),
        func.sum(WeeklyData.ipv).label('visitors'),
    ).filter(WeeklyData.week_start == week_start).first()
    
    return {
        "gmv": round(week_stats.gmv or 0, 2),
        "visitors": week_stats.visitors or 0
    }
