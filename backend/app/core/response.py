from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .logger import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    def __init__(self, code: int = 400, message: str = "Error", data=None):
        self.code = code
        self.message = message
        self.data = data


def success_response(data=None, message: str = "success", code: int = 200):
    return {"code": code, "message": message, "data": data}


def error_response(code: int = 400, message: str = "Error", data=None):
    return {"code": code, "message": message, "data": data}


def paginated_response(data=None, total: int = 0, page: int = 1, page_size: int = 20, message: str = "success"):
    return {
        "code": 200,
        "message": message,
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.code if exc.code >= 400 else 400,
        content=error_response(code=exc.code, message=exc.message, data=exc.data),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code=exc.status_code, message=str(exc.detail)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        errors.append(f"{field}: {error.get('msg', '')}")
    return JSONResponse(
        status_code=422,
        content=error_response(code=422, message="参数验证失败", data=errors),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=error_response(code=500, message="服务器内部错误"),
    )
