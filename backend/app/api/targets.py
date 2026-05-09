from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from fastapi import Depends, APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func
from app.core.database import get_db
from app.models.targets import ShopTarget, ProductTarget
from app.models import Product
from app.core.utils import safe_float

router = APIRouter(prefix="/targets", tags=["目标管理"])


@router.get("/shop", response_model=dict)
def get_shop_targets(
    year: Optional[int] = None,
    month: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ShopTarget)

    if year:
        query = query.filter(ShopTarget.period.like(f"{year}%"))
    if month:
        query = query.filter(ShopTarget.period == month)

    targets = query.order_by(ShopTarget.period.desc()).all()

    target_list = []
    for t in targets:
        target_list.append({
            "id": t.id,
            "target_month": t.period,
            "gmv_target": safe_float(t.target_gsv),
            "gmv_actual": 0,
            "gmv_progress": 0,
            "visitors_target": 0,
            "visitors_actual": 0,
            "visitors_progress": 0,
            "conversion_target": safe_float(t.target_conversion),
            "conversion_actual": 0,
            "conversion_progress": 0,
            "roi_target": safe_float(t.target_ad_ratio),
            "roi_actual": 0,
            "roi_progress": 0,
            "ad_spend_target": safe_float(t.target_ad_spend),
            "ad_spend_actual": 0,
            "ad_spend_progress": 0,
            "notes": t.remark,
            "created_at": t.created_at.isoformat() if t.created_at else ""
        })

    return {"code": 200, "data": target_list}


@router.get("/product", response_model=dict)
def get_product_targets(
    year: Optional[int] = None,
    month: Optional[str] = None,
    product_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ProductTarget)

    if year:
        query = query.filter(ProductTarget.period.like(f"{year}%"))
    if month:
        query = query.filter(ProductTarget.period == month)
    if product_id:
        query = query.filter(ProductTarget.product_id == product_id)

    targets = query.order_by(ProductTarget.period.desc()).all()

    target_list = []
    for t in targets:
        product = db.query(Product).filter(Product.product_id == t.product_id).first()
        target_list.append({
            "id": t.id,
            "product_id": t.product_id,
            "product_name": product.title if product else "",
            "target_month": t.period,
            "sales_target": safe_float(t.target_gsv),
            "sales_actual": 0,
            "sales_progress": 0,
            "gmv_target": safe_float(t.target_gsv),
            "gmv_actual": 0,
            "gmv_progress": 0,
            "roi_target": safe_float(t.target_ad_ratio),
            "roi_actual": 0,
            "roi_progress": 0,
            "notes": t.remark,
            "created_at": t.created_at.isoformat() if t.created_at else ""
        })

    return {"code": 200, "data": target_list}


class ShopTargetCreate(BaseModel):
    target_month: str
    gmv_target: float = 0
    visitors_target: int = 0
    conversion_target: float = 0
    roi_target: float = 0
    ad_spend_target: float = 0
    notes: Optional[str] = None


class ProductTargetCreate(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    target_month: str
    sales_target: float = 0
    gmv_target: float = 0
    roi_target: float = 0
    notes: Optional[str] = None


@router.post("/shop", response_model=dict)
def create_shop_target(
    data: ShopTargetCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(ShopTarget).filter(
        ShopTarget.period == data.target_month
    ).first()

    if existing:
        existing.target_gsv = data.gmv_target
        existing.target_conversion = data.conversion_target
        existing.target_ad_ratio = data.roi_target
        existing.target_ad_spend = data.ad_spend_target
        existing.remark = data.notes
        db.commit()
        return {"code": 200, "message": "目标已更新", "data": {"id": existing.id}}
    else:
        target = ShopTarget(
            period=data.target_month,
            target_gsv=data.gmv_target,
            target_conversion=data.conversion_target,
            target_ad_ratio=data.roi_target,
            target_ad_spend=data.ad_spend_target,
            remark=data.notes
        )
        db.add(target)
        db.commit()
        return {"code": 200, "message": "目标已创建", "data": {"id": target.id}}


@router.post("/product", response_model=dict)
def create_product_target(
    data: ProductTargetCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(ProductTarget).filter(
        ProductTarget.product_id == data.product_id,
        ProductTarget.period == data.target_month
    ).first()

    if existing:
        existing.target_gsv = data.gmv_target
        existing.target_ad_ratio = data.roi_target
        existing.remark = data.notes
        db.commit()
        return {"code": 200, "message": "目标已更新", "data": {"id": existing.id}}
    else:
        target = ProductTarget(
            product_id=data.product_id,
            period=data.target_month,
            target_gsv=data.gmv_target,
            target_ad_ratio=data.roi_target,
            remark=data.notes
        )
        db.add(target)
        db.commit()
        return {"code": 200, "message": "目标已创建", "data": {"id": target.id}}


@router.put("/shop/{target_id}", response_model=dict)
def update_shop_target(
    target_id: int,
    gmv_actual: Optional[float] = None,
    visitors_actual: Optional[int] = None,
    conversion_actual: Optional[float] = None,
    roi_actual: Optional[float] = None,
    ad_spend_actual: Optional[float] = None,
    db: Session = Depends(get_db)
):
    target = db.query(ShopTarget).filter(ShopTarget.id == target_id).first()
    if not target:
        return {"code": 404, "message": "目标不存在"}

    db.commit()
    return {"code": 200, "message": "目标已更新"}


@router.put("/product/{target_id}", response_model=dict)
def update_product_target(
    target_id: int,
    sales_actual: Optional[float] = None,
    gmv_actual: Optional[float] = None,
    roi_actual: Optional[float] = None,
    db: Session = Depends(get_db)
):
    target = db.query(ProductTarget).filter(ProductTarget.id == target_id).first()
    if not target:
        return {"code": 404, "message": "目标不存在"}

    db.commit()
    return {"code": 200, "message": "目标已更新"}


@router.delete("/shop/{target_id}", response_model=dict)
def delete_shop_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ShopTarget).filter(ShopTarget.id == target_id).first()
    if not target:
        return {"code": 404, "message": "目标不存在"}

    db.delete(target)
    db.commit()
    return {"code": 200, "message": "目标已删除"}


@router.delete("/product/{target_id}", response_model=dict)
def delete_product_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProductTarget).filter(ProductTarget.id == target_id).first()
    if not target:
        return {"code": 404, "message": "目标不存在"}

    db.delete(target)
    db.commit()
    return {"code": 200, "message": "目标已删除"}


@router.get("/comparison", response_model=dict)
def get_target_comparison(
    metric: str = Query("gmv", description="指标: gmv/visitors/conversion/roi"),
    months: int = Query(6, description="对比月份数"),
    db: Session = Depends(get_db)
):
    targets = db.query(ShopTarget).order_by(ShopTarget.period.desc()).limit(months).all()

    comparisons = []
    for t in reversed(targets):
        target_val = safe_float(t.target_gsv)
        actual_val = 0

        if metric == "gmv":
            target_val = safe_float(t.target_gsv)
        elif metric == "conversion":
            target_val = safe_float(t.target_conversion)
        elif metric == "roi":
            target_val = safe_float(t.target_ad_ratio)
        elif metric == "ad_spend":
            target_val = safe_float(t.target_ad_spend)

        progress = (actual_val / target_val * 100) if target_val else 0
        gap = target_val - actual_val

        comparisons.append({
            "month": t.period,
            "target": target_val,
            "actual": actual_val,
            "progress": round(progress, 2),
            "gap": gap
        })

    return {"code": 200, "data": comparisons}


@router.get("/summary", response_model=dict)
def get_target_summary(
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    shop_query = db.query(ShopTarget)
    product_query = db.query(ProductTarget)

    if year:
        shop_query = shop_query.filter(ShopTarget.period.like(f"{year}%"))
        product_query = product_query.filter(ProductTarget.period.like(f"{year}%"))

    shop_targets = shop_query.all()
    product_targets = product_query.all()

    total_targets = len(shop_targets) + len(product_targets)
    achieved_rate = 0
    avg_progress = 0
    overall_gap = 0

    if shop_targets:
        shop_gaps = [safe_float(t.target_gsv) for t in shop_targets]
        overall_gap = sum(shop_gaps)

    return {"code": 200, "data": {
        "total_targets": total_targets,
        "achieved_count": 0,
        "achieved_rate": 0,
        "avg_progress": 0,
        "overall_gap": overall_gap
    }}
