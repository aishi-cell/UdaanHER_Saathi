from fastapi import FastAPI

from app.config import get_settings

get_settings()

app = FastAPI(title="UdaanHer Saathi")
