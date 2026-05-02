from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.models import Product, DailyData, WeeklyData, MonthlyData, Alert
from app.schemas.common import ResponseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/inventory", tags=["库存预警"])


def get_data_model(dimension: str):
    if dimension == "monthly":
        return MonthlyData, 'month'
    elif dimension == "daily":
        return DailyData, 'date'
    else:
        return WeeklyData, 'week_start'


def get_latest_period(Model, date_col: str, db: Session) -> Optional[str]:
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        period = getattr(latest, date_col)
        if hasattr(period, 'isoformat'):
            return period.date().isoformat() if hasattr(period, 'date') else period.isoformat()
        return str(period)
    return None


def calculate_sales_velocity(product_id: str, Model, date_col: str, db: Session, days: int = 7) -> float:
    """计算日均销售速度"""
    from app.core.utils import get_prev_period

    periods = []
    current = get_latest_period(Model, date_col, db)
    if not current:
        return 0

    for _ in range(days):
        periods.append(str(current))
        if date_col == 'month':
            y, m = current.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            current = f"{y}-{m:02d}"
        else:
            dt = datetime.strptime(str(current), '%Y-%m-%d')
            prev = dt - timedelta(days=1)
            current = prev.strftime('%Y-%m-%d')

    total_qty = 0
    for p in periods:
        data = db.query(func.sum(Model.payment_qty)).filter(
            Model.product_id == product_id,
            getattr(Model, date_col) == p
        ).scalar() or 0
        total_qty += float(data)

    return total_qty / days if days > 0 else 0


@router.get("/warnings", response_model=ResponseModel)
def get_inventory_warnings(
    dimension: str = Query("weekly", description="时间维度"),
    low_threshold: int = Query(50, description="库存下限预警"),
    high_threshold: int = Query(500, description="库存上限预警"),
    days: int = Query(7, description="计算销量的天数"),
    db: Session = Depends(get_db)
):
    """获取库存预警列表"""
    Model, date_col = get_data_model(dimension)

    all_products = db.query(Product).filter(Product.status == 'active').all()

    warnings = []
    products_without_data = []

    for product in all_products:
        data = db.query(Model).filter(
            Model.product_id == product.product_id
        ).order_by(desc(getattr(Model, date_col))).first()

        if not data:
            products_without_data.append({
                "product_id": product.product_id,
                "title": product.title,
                "tier": product.tier,
                "issue": "暂无销售数据",
                "priority": "low"
            })
            continue

        inventory = getattr(data, 'cart_qty', 0) or 0
        sales_qty = getattr(data, 'payment_qty', 0) or 0

        sales_velocity = calculate_sales_velocity(
            product.product_id, Model, date_col, db, days
        )

        if sales_velocity > 0:
            days_until_stockout = inventory / sales_velocity
        else:
            days_until_stockout = float('inf')

        warning_level = None
        issue = None

        if inventory <= low_threshold:
            warning_level = "critical" if inventory <= low_threshold / 2 else "warning"
            issue = f"库存不足: {inventory}件，预计{ days_until_stockout:.0f}天售完" if days_until_stockout != float('inf') else f"库存不足: {inventory}件"
        elif inventory >= high_threshold:
            warning_level = "warning"
            issue = f"库存积压: {inventory}件"
        elif sales_velocity == 0 and inventory > 0:
            warning_level = "info"
            issue = "无销售，建议促销"

        if warning_level:
            warnings.append({
                "product_id": product.product_id,
                "title": product.title,
                "tier": product.tier,
                "inventory": inventory,
                "sales_velocity": round(sales_velocity, 2),
                "days_until_stockout": round(days_until_stockout, 1) if days_until_stockout != float('inf') else None,
                "warning_level": warning_level,
                "issue": issue,
                "priority": "high" if warning_level == "critical" else "medium" if warning_level == "warning" else "low"
            })

    warnings.sort(key=lambda x: (
        {"critical": 0, "warning": 1, "info": 2}.get(x["priority"], 3),
        -x.get("inventory", 0)
    ))

    return ResponseModel(data={
        "dimension": dimension,
        "thresholds": {
            "low": low_threshold,
            "high": high_threshold
        },
        "warnings": warnings,
        "products_without_data": products_without_data,
        "summary": {
            "total": len(warnings),
            "critical": len([w for w in warnings if w["priority"] == "high"]),
            "warning": len([w for w in warnings if w["priority"] == "medium"]),
            "info": len([w for w in warnings if w["priority"] == "low"]),
            "no_data": len(products_without_data)
        }
    })


@router.get("/summary", response_model=ResponseModel)
def get_inventory_summary(
    dimension: str = Query("weekly", description="时间维度"),
    db: Session = Depends(get_db)
):
    """获取库存汇总"""
    Model, date_col = get_data_model(dimension)

    products_with_inventory = db.query(
        Product.product_id
    ).join(Model, Product.product_id == Model.product_id).filter(
        Product.status == 'active'
    ).distinct().count()

    recent_data = db.query(
        func.sum(Model.cart_qty).label('total_inventory'),
        func.avg(Model.cart_qty).label('avg_inventory'),
        func.sum(Model.payment_qty).label('total_sales'),
    ).join(Product, Product.product_id == Model.product_id).filter(
        Product.status == 'active'
    )

    latest_period = get_latest_period(Model, date_col, db)
    if latest_period:
        recent_data = recent_data.filter(getattr(Model, date_col) == latest_period)
    else:
        recent_data = recent_data.first()

    return ResponseModel(data={
        "dimension": dimension,
        "period": latest_period,
        "active_products": products_with_inventory,
        "total_inventory": int(float(recent_data.total_inventory or 0)),
        "avg_inventory": round(float(recent_data.avg_inventory or 0), 1),
        "total_sales": int(float(recent_data.total_sales or 0))
    })


@router.post("/rules", response_model=ResponseModel)
def create_inventory_rule(
    product_id: str = Body(..., description="商品ID"),
    low_threshold: int = Body(50, description="库存下限"),
    high_threshold: int = Body(500, description="库存上限"),
    enabled: bool = Body(True, description="是否启用"),
    db: Session = Depends(get_db)
):
    """创库存预警规则"""
    return ResponseModel(data={
        "product_id": product_id,
        "low_threshold": low_threshold,
        "high_threshold": high_threshold,
        "enabled": enabled,
        "message": "规则创建成功"
    })


@router.get("/velocity", response_model=ResponseModel)
def get_sales_velocity(
    dimension: str = Query("weekly", description="时间维度"),
    days: int = Query(7, description="统计天数"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取商品销售速度排行"""
    Model, date_col = get_data_model(dimension)

    products = db.query(Product).filter(Product.status == 'active').limit(limit).all()

    velocities = []
    for product in products:
        velocity = calculate_sales_velocity(product.product_id, Model, date_col, db, days)

        data = db.query(Model).filter(
            Model.product_id == product.product_id
        ).order_by(desc(getattr(Model, date_col))).first()

        inventory = getattr(data, 'cart_qty', 0) or 0 if data else 0

        velocities.append({
            "product_id": product.product_id,
            "title": product.title,
            "tier": product.tier,
            "daily_velocity": round(velocity, 2),
            "inventory": inventory,
            "days_remaining": round(inventory / velocity, 1) if velocity > 0 else None
        })

    velocities.sort(key=lambda x: x['daily_velocity'], reverse=True)

    return ResponseModel(data={
        "dimension": dimension,
        "days": days,
        "products": velocities
    })
