from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os
import pathlib
import traceback

from app.core import settings, engine, Base
from app.core.logger import get_logger, setup_logging
from app.core.scheduler import scheduler
from app.core.response import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from app.core.middleware import RequestLoggingMiddleware, RateLimitMiddleware
from app.api import api_router
from app.api import realtime

# 初始化日志
setup_logging(log_level="DEBUG" if settings.DEBUG else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data/db", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/backups", exist_ok=True)
    os.makedirs("data/snapshots", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    scheduler.start()
    logger.info("Application startup complete")
    yield
    scheduler.shutdown()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
    redirect_slashes=False,
    description="""
## 海贝海数据仪表盘 API

电商数据分析平台的后端API服务。

### 功能模块

- **商品管理**: 商品列表、详情、分类管理
- **数据分析**: KPI分析、趋势分析、四象限分析
- **运营监控**: 健康度评分、异常告警、运营日志
- **智能工具**: 智能选品、自动报告、智能导入

### 认证方式

使用 JWT Bearer Token 认证。在请求头中添加：
```
Authorization: Bearer <token>
```

通过 `/api/auth/login` 获取 token。

### 数据格式

所有API返回JSON格式数据，遵循统一响应格式：
```json
{
  "data": {},
  "total": 0,
  "message": "success"
}
```
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# API routes first
app.include_router(api_router)
app.include_router(realtime.router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION
    }


# Mount frontend static files
frontend_dist = pathlib.Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    # Mount static files for assets (CSS, JS, etc.)
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    # Serve index.html for SPA routes (exclude API paths)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str, request: Request):
        # Skip API routes
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("health"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"detail": "Not Found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
