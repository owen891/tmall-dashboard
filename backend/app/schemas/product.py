from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


class ProductBase(BaseModel):
    product_id: str
    title: Optional[str] = None
    category: Optional[str] = None
    tier: Optional[str] = None
    style: Optional[str] = None
    scene: Optional[str] = None
    list_date: Optional[date] = None
    status: Optional[str] = "active"
    remark: Optional[str] = None
    image_url: Optional[str] = None
    manager: Optional[str] = None
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
    payment_amount: Optional[float] = 0
    refund_amount: Optional[float] = 0
    net_sales: Optional[float] = 0
    gsv_change: Optional[float] = 0
    ad_spend: Optional[float] = 0
    ad_spend_change: Optional[float] = 0
    total_roi: Optional[float] = 0
    direct_roi: Optional[float] = 0
    direct_roi_change: Optional[float] = 0
    refund_ad_ratio: Optional[float] = 0
    visitors: Optional[int] = 0
    uv_value: Optional[float] = 0
    payment_conversion: Optional[float] = 0
    refund_rate: Optional[float] = 0
    cart_rate: Optional[float] = 0
    cart_qty: Optional[int] = 0
    payment_users: Optional[int] = 0
    avg_order_value: Optional[float] = 0
    lead_potential_ratio: Optional[float] = 0
    new_customer_cost: Optional[float] = 0
    direct_cart_cost: Optional[float] = 0
    total_cart_cost: Optional[float] = 0
    repurchase_rate: Optional[float] = 0
    cross_sell_rate: Optional[float] = 0
    category_width: Optional[int] = 0
    click_rate: Optional[float] = 0
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
    note: str
    created_by: Optional[str] = "admin"


class ProductNoteCreate(ProductNoteBase):
    pass


class ProductNoteResponse(ProductNoteBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductTagBase(BaseModel):
    product_id: str
    tag: str
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
