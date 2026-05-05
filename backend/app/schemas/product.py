from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime


class ProductBase(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    title: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    tier: Optional[str] = None
    style: Optional[str] = Field(None, max_length=100)
    scene: Optional[str] = Field(None, max_length=100)
    list_date: Optional[date] = None
    status: Optional[str] = "active"
    remark: Optional[str] = Field(None, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=500)
    manager: Optional[str] = Field(None, max_length=50)
    starred: Optional[bool] = False


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    product_id: Optional[str] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WeeklyDataBase(BaseModel):
    product_id: str
    week_start: date
    payment_amount: Optional[float] = Field(0, ge=0)
    refund_amount: Optional[float] = Field(0, ge=0)
    net_sales: Optional[float] = 0
    gsv_change: Optional[float] = 0
    ad_spend: Optional[float] = Field(0, ge=0)
    ad_spend_change: Optional[float] = 0
    total_roi: Optional[float] = 0
    direct_roi: Optional[float] = 0
    direct_roi_change: Optional[float] = 0
    refund_ad_ratio: Optional[float] = 0
    visitors: Optional[int] = Field(0, ge=0)
    uv_value: Optional[float] = 0
    payment_conversion: Optional[float] = Field(0, ge=0, le=100)
    refund_rate: Optional[float] = Field(0, ge=0, le=100)
    cart_rate: Optional[float] = Field(0, ge=0, le=100)
    cart_qty: Optional[int] = Field(0, ge=0)
    payment_users: Optional[int] = Field(0, ge=0)
    avg_order_value: Optional[float] = Field(0, ge=0)
    lead_potential_ratio: Optional[float] = 0
    new_customer_cost: Optional[float] = 0
    direct_cart_cost: Optional[float] = 0
    total_cart_cost: Optional[float] = 0
    repurchase_rate: Optional[float] = Field(0, ge=0, le=100)
    cross_sell_rate: Optional[float] = Field(0, ge=0, le=100)
    category_width: Optional[int] = Field(0, ge=0)
    click_rate: Optional[float] = Field(0, ge=0, le=100)
    history_data: Optional[Dict[str, Any]] = None
    data_source: Optional[str] = None


class WeeklyDataCreate(WeeklyDataBase):
    pass


class WeeklyDataResponse(WeeklyDataBase):
    id: int
    imported_at: datetime
    
    class Config:
        from_attributes = True


class ProductWithData(BaseModel):
    product: ProductResponse
    latest_data: Optional[WeeklyDataResponse] = None
    health_score: Optional[float] = None


class OperationActionBase(BaseModel):
    product_id: str
    action_date: date
    action_type: Optional[str] = None
    action_detail: Optional[str] = None
    before_payment: Optional[float] = 0
    before_visitors: Optional[int] = 0
    before_conversion: Optional[float] = 0
    before_roi: Optional[float] = 0
    after_payment: Optional[float] = 0
    after_visitors: Optional[int] = 0
    after_conversion: Optional[float] = 0
    after_roi: Optional[float] = 0
    effectiveness_score: Optional[float] = 0


class OperationActionCreate(OperationActionBase):
    pass


class OperationActionResponse(OperationActionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductNoteBase(BaseModel):
    product_id: str
    note: str = Field(..., min_length=1, max_length=5000)
    created_by: Optional[str] = Field("admin", max_length=50)


class ProductNoteCreate(ProductNoteBase):
    pass


class ProductNoteResponse(ProductNoteBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductTagBase(BaseModel):
    product_id: str
    tag: str = Field(..., min_length=1, max_length=50)
    is_auto: Optional[bool] = False


class ProductTagCreate(ProductTagBase):
    pass


class ProductTagResponse(ProductTagBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductHealthBase(BaseModel):
    product_id: str
    period: str
    sales_score: Optional[float] = 0
    conversion_score: Optional[float] = 0
    roi_score: Optional[float] = 0
    refund_score: Optional[float] = 0
    growth_score: Optional[float] = 0
    review_score: Optional[float] = 0
    health_score: Optional[float] = 0
    health_level: Optional[str] = None
    alert_dimensions: Optional[List[str]] = None


class ProductHealthCreate(ProductHealthBase):
    pass


class ProductHealthResponse(ProductHealthBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
