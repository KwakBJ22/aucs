"""화면 오류 받기(출시 전 꼭, 10/29). 웹은 sendBeacon(text/plain)으로 보냄 — 사전 확인 없이 한 번에."""

import json
import re

from fastapi import APIRouter, Request, Response

from aucs_api.services import errors

router = APIRouter()
_ANON = re.compile(r"^[A-Za-z0-9-]{8,40}$")


@router.post("/errors", status_code=204)
async def post_error(request: Request) -> Response:
    raw = await request.body()
    if len(raw) > 8000:
        return Response(status_code=204)
    try:
        d = json.loads(raw or b"{}")
    except ValueError:
        return Response(status_code=204)
    msg = str(d.get("m") or "").strip()
    anon = str(d.get("a") or "")
    if not msg or not _ANON.match(anon):
        return Response(status_code=204)
    errors.save(
        "web", msg, path=d.get("p"), stack=d.get("s"), anon_id=anon,
        agent=request.headers.get("user-agent"),
    )  # fmt: skip
    return Response(status_code=204)
