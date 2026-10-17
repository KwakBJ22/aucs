"""연결 확인 주소."""

from typing import Any

from fastapi import APIRouter

from aucs_api.services.health import check_db

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/health/db")
def health_db() -> dict[str, Any]:
    return check_db()
