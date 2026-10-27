"""사용 기록(할 일 5, 10/27): 화면 이동·주요 동작만. 성공 지표(처음 판단까지 시간·관심 등록률·주간 재방문)용.

웹은 navigator.sendBeacon 으로 text/plain 을 보냄(사전 확인 없이 한 번에). 이름·이메일은 받지 않음.
토큰이 같이 오면 확인해서 user_id 로 남기고, 틀리면 익명으로.
"""

import json
import re

from fastapi import APIRouter, HTTPException, Request, Response

from aucs_api.auth.user import current_user_id
from aucs_api.db import connect

router = APIRouter()
KINDS = {"view", "start_done", "item_view", "watch_add", "calc", "bid_sheet", "login", "alert_on"}
_ANON = re.compile(r"^[A-Za-z0-9-]{8,40}$")


@router.post("/events", status_code=204)
async def post_event(request: Request) -> Response:
    raw = await request.body()
    if len(raw) > 4000:
        return Response(status_code=204)
    try:
        d = json.loads(raw or b"{}")
    except ValueError:
        return Response(status_code=204)
    kind, anon = str(d.get("k") or ""), str(d.get("a") or "")
    if kind not in KINDS or not _ANON.match(anon):
        return Response(status_code=204)
    uid = None
    if tok := d.get("t"):
        try:
            uid = current_user_id(f"Bearer {tok}")
        except HTTPException:
            uid = None
    path = str(d.get("p") or "")[:200] or None
    item = str(d.get("i") or "")[:80] or None
    with connect() as c:
        c.execute(
            "insert into app.events (anon_id, user_id, kind, path, item_id) values (%s, %s, %s, %s, %s)",
            (anon, uid, kind, path, item),
        )
    return Response(status_code=204)
