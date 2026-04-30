from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional, Dict, Any

T = TypeVar('T')


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
    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    search: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


class HealthCheckResponse(BaseModel):
    status: str = "ok"
    version: str
