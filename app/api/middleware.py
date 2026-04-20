import time
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.api.dependencies import require_global_rate_limit
from app.config.logging_config import get_logger
from app.config.settings import settings


logger = get_logger(__name__)


async def global_rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    require_global_rate_limit(request)
    return await call_next(request)


async def log_requests(request: Request, call_next):
    """Loga todas as requisições HTTP com método, path, status e latência."""
    t0 = time.time()
    response = await call_next(request)
    elapsed = round(time.time() - t0, 3)

    log = logger.warning if response.status_code >= 400 else logger.info
    log(
        "HTTP request",
        extra={
            "action": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_seconds": elapsed,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return response


EXCLUDED_PATHS = {
    "/docs",
    "/openapi.json",
    "/health",
}


async def api_key_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)

    api_key = request.headers.get("x-api-key")

    if not api_key or api_key != settings.API_KEY:
        response = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden"},
        )

        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"

        return response

    return await call_next(request)
