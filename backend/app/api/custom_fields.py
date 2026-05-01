from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.models import ProductCustomField

router = APIRouter(prefix="/custom-fields", tags=["自定义字段"])


class CustomFieldCreate(BaseModel):
    product_id: str
    field_key: str
    field_value: Optional[str] = None
    field_type: str = "text"


class CustomFieldUpdate(BaseModel):
    field_value: Optional[str] = None
    field_type: Optional[str] = None


class CustomFieldResponse(BaseModel):
    id: int
    product_id: str
    field_key: str
    field_value: Optional[str]
    field_type: str

    class Config:
        from_attributes = True


class CustomFieldsBatchUpdate(BaseModel):
    product_id: str
    fields: List[dict]


@router.post("/", response_model=dict)
def create_custom_field(data: CustomFieldCreate, db: Session = Depends(get_db)):
    existing = db.query(ProductCustomField).filter(
        ProductCustomField.product_id == data.product_id,
        ProductCustomField.field_key == data.field_key
    ).first()
    
    if existing:
        existing.field_value = data.field_value
        existing.field_type = data.field_type
        db.commit()
        db.refresh(existing)
        return {"message": "字段已更新", "field": {
            "id": existing.id,
            "product_id": existing.product_id,
            "field_key": existing.field_key,
            "field_value": existing.field_value,
            "field_type": existing.field_type
        }}
    
    field = ProductCustomField(
        product_id=data.product_id,
        field_key=data.field_key,
        field_value=data.field_value,
        field_type=data.field_type
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    
    return {"message": "字段已创建", "field": {
        "id": field.id,
        "product_id": field.product_id,
        "field_key": field.field_key,
        "field_value": field.field_value,
        "field_type": field.field_type
    }}


@router.get("/{product_id}", response_model=dict)
def get_product_custom_fields(product_id: str, db: Session = Depends(get_db)):
    fields = db.query(ProductCustomField).filter(
        ProductCustomField.product_id == product_id
    ).all()
    
    result = {}
    for f in fields:
        result[f.field_key] = {
            "value": f.field_value,
            "type": f.field_type,
            "id": f.id
        }
    
    return {"product_id": product_id, "fields": result}


@router.put("/{product_id}", response_model=dict)
def batch_update_custom_fields(product_id: str, data: CustomFieldsBatchUpdate, db: Session = Depends(get_db)):
    updated = []
    
    for field_data in data.fields:
        field_key = field_data.get("key")
        field_value = field_data.get("value")
        field_type = field_data.get("type", "text")
        
        existing = db.query(ProductCustomField).filter(
            ProductCustomField.product_id == product_id,
            ProductCustomField.field_key == field_key
        ).first()
        
        if existing:
            existing.field_value = field_value
            existing.field_type = field_type
            updated.append(existing)
        else:
            new_field = ProductCustomField(
                product_id=product_id,
                field_key=field_key,
                field_value=field_value,
                field_type=field_type
            )
            db.add(new_field)
            updated.append(new_field)
    
    db.commit()
    
    return {"message": f"已更新 {len(updated)} 个字段", "count": len(updated)}


@router.delete("/{product_id}/{field_key}", response_model=dict)
def delete_custom_field(product_id: str, field_key: str, db: Session = Depends(get_db)):
    field = db.query(ProductCustomField).filter(
        ProductCustomField.product_id == product_id,
        ProductCustomField.field_key == field_key
    ).first()
    
    if field:
        db.delete(field)
        db.commit()
        return {"message": "字段已删除"}
    
    return {"message": "字段不存在"}


@router.get("/keys/list", response_model=dict)
def list_all_field_keys(db: Session = Depends(get_db)):
    fields = db.query(ProductCustomField.field_key).distinct().all()
    keys = [f[0] for f in fields]
    return {"keys": keys}


@router.get("/all/values", response_model=dict)
def get_all_custom_fields(db: Session = Depends(get_db)):
    fields = db.query(ProductCustomField).all()
    result = {}
    for f in fields:
        if f.product_id not in result:
            result[f.product_id] = {}
        result[f.product_id][f.field_key] = {
            "value": f.field_value,
            "type": f.field_type
        }
    
    return {"data": result}
