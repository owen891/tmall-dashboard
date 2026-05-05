from pydantic import BaseModel, Field, field_validator
from typing import Generic, TypeVar, List, Optional, Dict, Any, Literal

T = TypeVar('T')

DimensionType = Literal["daily", "weekly", "monthly"]


class ResponseModel(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class ListResponseModel(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class PaginatedQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    search: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


class HealthCheckResponse(BaseModel):
    status: str = "ok"
    version: str
