"""Vercel 예약 실행(Cron) 주소(11/3): 알림을 PC 와 상관없이 제때 보냄.

Vercel 이 `Authorization: Bearer <CRON_SECRET>` 을 붙여 부름. 비밀값이 없거나 틀리면 막음.
시각은 vercel.json(협정 세계시 UTC) — 입찰일 아침 7:30(한국) = 22:30 UTC.
"""

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from aucs_api import settings

router = APIRouter(prefix="/cron")


def _check(authorization: str) -> None:
    want = f"Bearer {settings.CRON_SECRET}"
    if not settings.CRON_SECRET or not secrets.compare_digest(authorization, want):
        raise HTTPException(status_code=401, detail="예약 실행만 부를 수 있어요")


@router.get("/notify")
def cron_notify(authorization: str = Header(default=""), morning: bool = False) -> dict[str, Any]:
    _check(authorization)
    from aucs_workers.jobs.notify import run_once

    return {"ok": True, "result": run_once(morning=morning)}
