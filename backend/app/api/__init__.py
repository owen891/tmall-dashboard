from fastapi import APIRouter
from .products import router as products_router
from .imports import router as imports_router
from .dashboard import router as dashboard_router

api_router = APIRouter(prefix="/api")

api_router.include_router(products_router)
api_router.include_router(imports_router)
api_router.include_router(dashboard_router)
