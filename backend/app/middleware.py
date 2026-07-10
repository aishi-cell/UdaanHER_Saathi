import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("udaanher.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "%s %s %s %sms",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
            )
