from fastapi import APIRouter
from app.api import products, imports, dashboard, custom_fields, kpi, trends, ads, health, operations, lifecycle, refunds, targets, alerts, reviews, market, toolbox

api_router = APIRouter(prefix="/api")

api_router.include_router(products.router)
api_router.include_router(imports.router)
api_router.include_router(dashboard.router)
api_router.include_router(custom_fields.router)
api_router.include_router(kpi.router)
api_router.include_router(trends.router)
api_router.include_router(ads.router)
api_router.include_router(health.router)
api_router.include_router(operations.router)
api_router.include_router(lifecycle.router)
api_router.include_router(refunds.router)
api_router.include_router(targets.router)
api_router.include_router(alerts.router)
api_router.include_router(reviews.router)
api_router.include_router(market.router)
api_router.include_router(toolbox.router)
