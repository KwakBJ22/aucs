"""관리자 주소 (ADM-01). 라우터는 서비스만 부릅니다."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aucs_api.auth.admin import require_admin
from aucs_api.services import admin

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


class FlagIn(BaseModel):
    enabled: bool


@router.get("/status")
def get_status() -> dict[str, Any]:
    return admin.status()


@router.get("/review")
def get_review() -> dict[str, Any]:
    return admin.review_queue()


@router.get("/flags")
def get_flags() -> list[dict[str, Any]]:
    return admin.flags()


@router.put("/flags/{key}")
def put_flag(key: str, body: FlagIn) -> dict[str, Any]:
    row = admin.set_flag(key, body.enabled)
    if row is None:
        raise HTTPException(status_code=404, detail="없는 설정")
    return row


@router.get("/rule-tables")
def get_rule_tables() -> list[dict[str, Any]]:
    return admin.rule_tables()
