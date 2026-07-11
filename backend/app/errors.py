from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _add_cors_headers(request: Request, response: JSONResponse) -> None:
    # Starlette's CORSMiddleware never runs for responses produced by
    # app.add_exception_handler(Exception, ...) -- those are handled by
    # ServerErrorMiddleware, which sits *outside* CORSMiddleware in the
    # stack. Without this, a 500 during a cross-origin request shows up in
    # the browser as a misleading "blocked by CORS policy" error that hides
    # the real failure.
    origin = request.headers.get("origin")
    if not origin:
        return
    allowed_origins = [o.strip() for o in get_settings().cors_origins.split(",")]
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    response = JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))
    _add_cors_headers(request, response)
    return response


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("internal_error", "Something went wrong."),
    )
    _add_cors_headers(request, response)
    return response
