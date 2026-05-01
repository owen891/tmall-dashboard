from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func
from app.core.database import get_db
from app.models.product import ShopTarget, ProductTarget, Product

router = APIRouter(prefix="/targets", tags=["目标管理"])


class ShopTargetResponse(BaseModel):
    id: int
    target_month: str
    gmv_target: float
    gmv_actual: float
    gmv_progress: float
    visitors_target: int
    visitors_actual: int
    visitors_progress: float
    conversion_target: float
    conversion_actual: float
    conversion_progress: float
    roi_target: float
    roi_actual: float
    roi_progress: float
    ad_spend_target: float
    ad_spend_actual: float
    ad_spend_progress: float
    notes: Optional[str]
    created_at: str


class ProductTargetResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    target_month: str
    sales_target: float
    sales_actual: float
    sales_progress: float
    gmv_target: float
    gmv_actual: float
    gmv_progress: float
    roi_target: float
    roi_actual: float
    roi_progress: float
    notes: Optional[str]
    created_at: str


class TargetComparison(BaseModel):
    month: str
    target: float
    actual: float
    progress: float
    gap: float


class TargetSummary(BaseModel):
    total_targets: int
    achieved_count: int
    achieved_rate: float
    avg_progress: float
    overall_gap: float


@router.get("/shop", response_model=dict)
def get_shop_targets(
    year: Optional[int] = None,
    month: Optional[str] = None
):
    db = next(get_db())
    try:
        query = db.query(ShopTarget)

        if year:
            query = query.filter(ShopTarget.target_month.like(f"{year}%"))
        if month:
            query = query.filter(ShopTarget.target_month == month)

        targets = query.order_by(ShopTarget.target_month.desc()).all()

        target_list = []
        for t in targets:
            gmv_progress = (t.gmv_actual / t.gmv_target * 100) if t.gmv_target else 0
            visitors_progress = (t.visitors_actual / t.visitors_target * 100) if t.visitors_target else 0
            conversion_progress = (t.conversion_actual / t.conversion_target * 100) if t.conversion_target else 0
            roi_progress = (t.roi_actual / t.roi_target * 100) if t.roi_target else 0
            ad_spend_progress = (t.ad_spend_actual / t.ad_spend_target * 100) if t.ad_spend_target else 0

            target_list.append(ShopTargetResponse(
                id=t.id,
                target_month=t.target_month,
                gmv_target=t.gmv_target,
                gmv_actual=t.gmv_actual,
                gmv_progress=round(gmv_progress, 2),
                visitors_target=t.visitors_target,
                visitors_actual=t.visitors_actual,
                visitors_progress=round(visitors_progress, 2),
                conversion_target=t.conversion_target,
                conversion_actual=t.conversion_actual,
                conversion_progress=round(conversion_progress, 2),
                roi_target=t.roi_target,
                roi_actual=t.roi_actual,
                roi_progress=round(roi_progress, 2),
                ad_spend_target=t.ad_spend_target,
                ad_spend_actual=t.ad_spend_actual,
                ad_spend_progress=round(ad_spend_progress, 2),
                notes=t.notes,
                created_at=t.created_at.isoformat() if t.created_at else ""
            ))

        return {"code": 200, "data": target_list}

    finally:
        db.close()


@router.get("/product", response_model=dict)
def get_product_targets(
    year: Optional[int] = None,
    month: Optional[str] = None,
    product_id: Optional[int] = None
):
    db = next(get_db())
    try:
        query = db.query(ProductTarget)

        if year:
            query = query.filter(ProductTarget.target_month.like(f"{year}%"))
        if month:
            query = query.filter(ProductTarget.target_month == month)
        if product_id:
            query = query.filter(ProductTarget.product_id == product_id)

        targets = query.order_by(ProductTarget.target_month.desc()).all()

        target_list = []
        for t in targets:
            sales_progress = (t.sales_actual / t.sales_target * 100) if t.sales_target else 0
            gmv_progress = (t.gmv_actual / t.gmv_target * 100) if t.gmv_target else 0
            roi_progress = (t.roi_actual / t.roi_target * 100) if t.roi_target else 0

            target_list.append(ProductTargetResponse(
                id=t.id,
                product_id=t.product_id,
                product_name=t.product_name,
                target_month=t.target_month,
                sales_target=t.sales_target,
                sales_actual=t.sales_actual,
                sales_progress=round(sales_progress, 2),
                gmv_target=t.gmv_target,
                gmv_actual=t.gmv_actual,
                gmv_progress=round(gmv_progress, 2),
                roi_target=t.roi_target,
                roi_actual=t.roi_actual,
                roi_progress=round(roi_progress, 2),
                notes=t.notes,
                created_at=t.created_at.isoformat() if t.created_at else ""
            ))

        return {"code": 200, "data": target_list}

    finally:
        db.close()


@router.post("/shop", response_model=dict)
def create_shop_target(
    target_month: str,
    gmv_target: float = 0,
    visitors_target: int = 0,
    conversion_target: float = 0,
    roi_target: float = 0,
    ad_spend_target: float = 0,
    notes: Optional[str] = None
):
    db = next(get_db())
    try:
        existing = db.query(ShopTarget).filter(
            ShopTarget.target_month == target_month
        ).first()

        if existing:
            existing.gmv_target = gmv_target
            existing.visitors_target = visitors_target
            existing.conversion_target = conversion_target
            existing.roi_target = roi_target
            existing.ad_spend_target = ad_spend_target
            existing.notes = notes
            db.commit()
            return {"code": 200, "message": "目标已更新", "data": {"id": existing.id}}
        else:
            target = ShopTarget(
                target_month=target_month,
                gmv_target=gmv_target,
                visitors_target=visitors_target,
                conversion_target=conversion_target,
                roi_target=roi_target,
                ad_spend_target=ad_spend_target,
                notes=notes
            )
            db.add(target)
            db.commit()
            return {"code": 200, "message": "目标已创建", "data": {"id": target.id}}

    finally:
        db.close()


@router.post("/product", response_model=dict)
def create_product_target(
    product_id: int,
    product_name: str,
    target_month: str,
    sales_target: float = 0,
    gmv_target: float = 0,
    roi_target: float = 0,
    notes: Optional[str] = None
):
    db = next(get_db())
    try:
        existing = db.query(ProductTarget).filter(
            ProductTarget.product_id == product_id,
            ProductTarget.target_month == target_month
        ).first()

        if existing:
            existing.sales_target = sales_target
            existing.gmv_target = gmv_target
            existing.roi_target = roi_target
            existing.notes = notes
            db.commit()
            return {"code": 200, "message": "目标已更新", "data": {"id": existing.id}}
        else:
            target = ProductTarget(
                product_id=product_id,
                product_name=product_name,
                target_month=target_month,
                sales_target=sales_target,
                gmv_target=gmv_target,
                roi_target=roi_target,
                notes=notes
            )
            db.add(target)
            db.commit()
            return {"code": 200, "message": "目标已创建", "data": {"id": target.id}}

    finally:
        db.close()


@router.put("/shop/{target_id}", response_model=dict)
def update_shop_target(
    target_id: int,
    gmv_actual: Optional[float] = None,
    visitors_actual: Optional[int] = None,
    conversion_actual: Optional[float] = None,
    roi_actual: Optional[float] = None,
    ad_spend_actual: Optional[float] = None
):
    db = next(get_db())
    try:
        target = db.query(ShopTarget).filter(ShopTarget.id == target_id).first()
        if not target:
            return {"code": 404, "message": "目标不存在"}

        if gmv_actual is not None:
            target.gmv_actual = gmv_actual
        if visitors_actual is not None:
            target.visitors_actual = visitors_actual
        if conversion_actual is not None:
            target.conversion_actual = conversion_actual
        if roi_actual is not None:
            target.roi_actual = roi_actual
        if ad_spend_actual is not None:
            target.ad_spend_actual = ad_spend_actual

        db.commit()
        return {"code": 200, "message": "目标已更新"}

    finally:
        db.close()


@router.put("/product/{target_id}", response_model=dict)
def update_product_target(
    target_id: int,
    sales_actual: Optional[float] = None,
    gmv_actual: Optional[float] = None,
    roi_actual: Optional[float] = None
):
    db = next(get_db())
    try:
        target = db.query(ProductTarget).filter(ProductTarget.id == target_id).first()
        if not target:
            return {"code": 404, "message": "目标不存在"}

        if sales_actual is not None:
            target.sales_actual = sales_actual
        if gmv_actual is not None:
            target.gmv_actual = gmv_actual
        if roi_actual is not None:
            target.roi_actual = roi_actual

        db.commit()
        return {"code": 200, "message": "目标已更新"}

    finally:
        db.close()


@router.delete("/shop/{target_id}", response_model=dict)
def delete_shop_target(target_id: int):
    db = next(get_db())
    try:
        target = db.query(ShopTarget).filter(ShopTarget.id == target_id).first()
        if not target:
            return {"code": 404, "message": "目标不存在"}

        db.delete(target)
        db.commit()
        return {"code": 200, "message": "目标已删除"}

    finally:
        db.close()


@router.delete("/product/{target_id}", response_model=dict)
def delete_product_target(target_id: int):
    db = next(get_db())
    try:
        target = db.query(ProductTarget).filter(ProductTarget.id == target_id).first()
        if not target:
            return {"code": 404, "message": "目标不存在"}

        db.delete(target)
        db.commit()
        return {"code": 200, "message": "目标已删除"}

    finally:
        db.close()


@router.get("/comparison", response_model=dict)
def get_target_comparison(
    metric: str = Query("gmv", description="指标: gmv/visitors/conversion/roi"),
    months: int = Query(6, description="对比月份数")
):
    db = next(get_db())
    try:
        targets = db.query(ShopTarget).order_by(ShopTarget.target_month.desc()).limit(months).all()

        comparisons = []
        for t in reversed(targets):
            if metric == "gmv":
                target = t.gmv_target
                actual = t.gmv_actual
            elif metric == "visitors":
                target = t.visitors_target
                actual = t.visitors_actual
            elif metric == "conversion":
                target = t.conversion_target
                actual = t.conversion_actual
            elif metric == "roi":
                target = t.roi_target
                actual = t.roi_actual
            else:
                target = t.gmv_target
                actual = t.gmv_actual

            progress = (actual / target * 100) if target else 0
            gap = target - actual

            comparisons.append(TargetComparison(
                month=t.target_month,
                target=target,
                actual=actual,
                progress=round(progress, 2),
                gap=gap
            ))

        return {"code": 200, "data": comparisons}

    finally:
        db.close()


@router.get("/summary", response_model=dict)
def get_target_summary(year: Optional[int] = None):
    db = next(get_db())
    try:
        shop_query = db.query(ShopTarget)
        product_query = db.query(ProductTarget)

        if year:
            shop_query = shop_query.filter(ShopTarget.target_month.like(f"{year}%"))
            product_query = product_query.filter(ProductTarget.target_month.like(f"{year}%"))

        shop_targets = shop_query.all()
        product_targets = product_query.all()

        total_shop_targets = len(shop_targets)
        total_product_targets = len(product_targets)
        total_targets = total_shop_targets + total_product_targets

        achieved_shop = sum(1 for t in shop_targets if t.gmv_actual >= t.gmv_target if t.gmv_target)
        achieved_product = sum(1 for t in product_targets if t.gmv_actual >= t.gmv_target if t.gmv_target)
        achieved_count = achieved_shop + achieved_product

        achieved_rate = (achieved_count / total_targets * 100) if total_targets else 0

        shop_progress = [((t.gmv_actual / t.gmv_target * 100) if t.gmv_target else 0) for t in shop_targets]
        product_progress = [((t.gmv_actual / t.gmv_target * 100) if t.gmv_target else 0) for t in product_targets]
        all_progress = shop_progress + product_progress
        avg_progress = sum(all_progress) / len(all_progress) if all_progress else 0

        shop_gaps = [(t.gmv_target - t.gmv_actual) for t in shop_targets if t.gmv_target]
        product_gaps = [(t.gmv_target - t.gmv_actual) for t in product_targets if t.gmv_target]
        overall_gap = sum(shop_gaps) + sum(product_gaps)

        summary = TargetSummary(
            total_targets=total_targets,
            achieved_count=achieved_count,
            achieved_rate=round(achieved_rate, 2),
            avg_progress=round(avg_progress, 2),
            overall_gap=overall_gap
        )

        return {"code": 200, "data": summary}

    finally:
        db.close()
