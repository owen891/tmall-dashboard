from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
import os
from uuid import uuid4

from app.core import get_db, settings
from app.models import Product, WeeklyData
from app.schemas import (
    ProductResponse,
    WeeklyDataResponse,
    OperationActionResponse,
    ProductNoteResponse,
    ProductTagResponse,
    ResponseModel,
    ListResponseModel,
    MessageResponse
)
from app.services import ProductService, ExcelImportService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=ListResponseModel[ProductResponse])
def get_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    tier: Optional[str] = None,
    style: Optional[str] = None,
    scene: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    service = ProductService(db)
    products, total = service.get_products(
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        tier=tier,
        style=style,
        scene=scene,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return ListResponseModel(
        data=products,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{product_id}", response_model=ResponseModel[ProductResponse])
def get_product(product_id: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    product = service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return ResponseModel(data=product)


@router.get("/{product_id}/weekly-data", response_model=ListResponseModel[WeeklyDataResponse])
def get_product_weekly_data(product_id: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    data = service.get_all_weekly_data(product_id)
    return ListResponseModel(data=data, total=len(data), page=1, page_size=100)


@router.get("/{product_id}/operations", response_model=ListResponseModel[OperationActionResponse])
def get_product_operations(product_id: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    actions = service.get_operations(product_id)
    return ListResponseModel(data=actions, total=len(actions), page=1, page_size=100)


@router.get("/{product_id}/notes", response_model=ListResponseModel[ProductNoteResponse])
def get_product_notes(product_id: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    notes = service.get_notes(product_id)
    return ListResponseModel(data=notes, total=len(notes), page=1, page_size=100)


@router.get("/{product_id}/tags", response_model=ListResponseModel[ProductTagResponse])
def get_product_tags(product_id: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    tags = service.get_tags(product_id)
    return ListResponseModel(data=tags, total=len(tags), page=1, page_size=100)


@router.post("/{product_id}/star", response_model=ResponseModel[ProductResponse])
def toggle_product_star(product_id: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    product = service.toggle_star(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return ResponseModel(data=product)


@router.post("/{product_id}/tags", response_model=ResponseModel[ProductTagResponse])
def add_product_tag(product_id: str, tag: str = Query(...), db: Session = Depends(get_db)):
    service = ProductService(db)
    from app.schemas import ProductTagCreate
    tag_obj = service.add_tag(ProductTagCreate(product_id=product_id, tag=tag))
    return ResponseModel(data=tag_obj)


@router.delete("/{product_id}/tags/{tag}", response_model=ResponseModel)
def remove_product_tag(product_id: str, tag: str, db: Session = Depends(get_db)):
    service = ProductService(db)
    success = service.remove_tag(product_id, tag)
    if not success:
        raise HTTPException(status_code=404, detail="标签不存在")
    return ResponseModel(message="删除成功")


@router.get("/filters/options", response_model=ResponseModel)
def get_filter_options(db: Session = Depends(get_db)):
    service = ProductService(db)
    return ResponseModel(data={
        "categories": service.get_categories(),
        "tiers": service.get_tiers(),
        "styles": service.get_styles(),
        "scenes": service.get_scenes()
    })
