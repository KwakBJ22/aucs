"""옥스 API 시작점. 실행: uv run uvicorn aucs_api.main:app --port 8100"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aucs_api import settings
from aucs_api.routers import admin, health, items, me

app = FastAPI(title="옥스 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.WEB_ORIGINS,
    allow_methods=["GET", "PUT", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(items.router)
app.include_router(me.router)
