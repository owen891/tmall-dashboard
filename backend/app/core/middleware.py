import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from .logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = (time.time() - start_time) * 1000
        
        if not request.url.path.startswith('/api/realtime'):
            logger.info(
                f"{request.method} {request.url.path} "
                f"- {response.status_code} "
                f"- {duration:.1f}ms"
            )
        
        if duration > 3000:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"- {duration:.1f}ms"
            )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith('/api/realtime'):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        if client_ip not in self._requests:
            self._requests[client_ip] = []
        
        self._requests[client_ip] = [
            t for t in self._requests[client_ip]
            if now - t < self.window_seconds
        ]
        
        if len(self._requests[client_ip]) >= self.max_requests:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"code": 429, "message": "请求过于频繁，请稍后再试"}
            )
        
        self._requests[client_ip].append(now)
        
        if len(self._requests) > 10000:
            oldest_key = min(self._requests, key=lambda k: min(self._requests[k]))
            del self._requests[oldest_key]
        
        return await call_next(request)
