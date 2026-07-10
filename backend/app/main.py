import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import ApiError, api_error_handler, unhandled_error_handler
from app.middleware import RequestLogMiddleware

logging.basicConfig(level=logging.INFO)

settings = get_settings()

APP_VERSION = "0.1.0"

app = FastAPI(title="UdaanHer Saathi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": APP_VERSION}
