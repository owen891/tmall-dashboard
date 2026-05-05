from fastapi import APIRouter, Query, Depends
from sqlalchemy import func
from app.models import Product, ProductLifecycle, WeeklyData, DailyData, MonthlyData
from app.core.database import get_db
from typing import Optional

router = APIRouter(prefix="/api/lifecycle", tags=["生命周期分析"])

@router.get("/stats")
async def get_lifecycle_stats(db=Depends(get_db)):
    """获取生命周期统计数据"""
    total_products = db.query(Product).count()

    products_with_lifecycle = db.query(ProductLifecycle).filter(
        ProductLifecycle.gsv_25_total > 0
    ).count()

    new_products = db.query(Product).filter(
        Product.list_date.isnot(None)
    ).count()

    return {
        "new": new_products,
        "growing": products_with_lifecycle,
        "mature": 0,
        "declining": 0,
        "total": total_products
    }

@router.get("/distribution")
async def get_lifecycle_distribution(db=Depends(get_db)):
    """获取生命周期分布数据 - 按月统计"""
    lifecycle_data = db.query(ProductLifecycle).filter(
        ProductLifecycle.gsv_25_total > 0
    ).all()

    months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    new_series = []
    growing_series = []
    mature_series = []
    declining_series = []

    for month in months:
        gsv_field_25 = getattr(ProductLifecycle, f'gsv_25_{month}', None)
        gsv_field_26 = getattr(ProductLifecycle, f'gsv_26_{month}', None)

        if gsv_field_25 is not None:
            month_data = db.query(ProductLifecycle).filter(
                getattr(ProductLifecycle, f'gsv_25_{month}') > 0
            ).count()
        else:
            month_data = 0

        new_series.append(month_data)
        growing_series.append(month_data)
        mature_series.append(0)
        declining_series.append(0)

    return {
        "labels": [f"{m}月" for m in months],
        "series": {
            "new": new_series,
            "growing": growing_series,
            "mature": mature_series,
            "declining": declining_series
        }
    }

@router.get("/products")
async def get_lifecycle_products(
    stage: Optional[str] = Query(None),
    db=Depends(get_db)
):
    """获取各生命周期阶段的产品列表"""
    query = db.query(
        Product.product_id,
        Product.title,
        Product.category,
        Product.tier,
        Product.image_url,
        ProductLifecycle.gsv_25_total,
        ProductLifecycle.gsv_26_total,
        ProductLifecycle.lifecycle_stage
    ).outerjoin(
        ProductLifecycle, Product.product_id == ProductLifecycle.product_id
    )

    if stage == 'new':
        query = query.filter(Product.list_date.isnot(None))
    elif stage == 'growing':
        query = query.filter(ProductLifecycle.gsv_25_total > 0)
    elif stage == 'mature':
        query = query.filter(ProductLifecycle.gsv_25_total > 10000)
    elif stage == 'declining':
        query = query.filter(ProductLifecycle.gsv_26_total < ProductLifecycle.gsv_25_total * 0.5)

    products = query.limit(50).all()

    result = []
    for p in products:
        result.append({
            "product_id": p.product_id,
            "name": p.title or "未命名",
            "category": p.category or "",
            "tier": p.tier or "",
            "image_url": p.image_url,
            "gsv_25_total": p.gsv_25_total or 0,
            "gsv_26_total": p.gsv_26_total or 0,
            "lifecycle_stage": p.lifecycle_stage or "新品"
        })

    return {"products": result}
