"""내 자료 주소 (로그인 필요). 라우터는 서비스만 부릅니다."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aucs_api import settings
from aucs_api.auth.user import current_user_id
from aucs_api.services import me

router = APIRouter(prefix="/me")
Uid = Annotated[str, Depends(current_user_id)]


class SearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    filters: dict[str, Any]
    delivery: str = Field(default="daily", pattern="^(instant|daily)$")


class PushIn(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class ProfileIn(BaseModel):
    regions: list[str] = []
    cash: int | None = None
    purpose: str | None = None


@router.get("/watch")
def get_watch(uid: Uid) -> list[dict[str, Any]]:
    return me.watch_list(uid, date.today())


@router.get("/watch/ids")
def get_watch_ids(uid: Uid) -> list[str]:
    return me.watch_ids(uid)


@router.put("/watch/{item_id}")
def put_watch(item_id: str, uid: Uid) -> dict[str, bool]:
    me.watch_add(uid, item_id)
    return {"ok": True}


@router.delete("/watch/{item_id}")
def delete_watch(item_id: str, uid: Uid) -> dict[str, bool]:
    me.watch_remove(uid, item_id)
    return {"ok": True}


@router.get("/searches")
def get_searches(uid: Uid) -> list[dict[str, Any]]:
    return me.searches(uid)


@router.post("/searches")
def post_search(body: SearchIn, uid: Uid) -> dict[str, Any] | None:
    return me.search_add(uid, body.name, body.filters, body.delivery)


@router.delete("/searches/{search_id}")
def delete_search(search_id: int, uid: Uid) -> dict[str, bool]:
    me.search_remove(uid, search_id)
    return {"ok": True}


@router.get("/push/key")
def get_push_key() -> dict[str, str]:
    return {"key": settings.VAPID_PUBLIC_KEY}


@router.post("/push")
def post_push(body: PushIn, uid: Uid) -> dict[str, bool]:
    me.push_add(uid, body.endpoint, body.p256dh, body.auth)
    return {"ok": True}


@router.get("/notifications")
def get_notifications(uid: Uid) -> list[dict[str, Any]]:
    return me.notifications(uid)


@router.put("/profile")
def put_profile(body: ProfileIn, uid: Uid) -> dict[str, bool]:
    me.save_profile(uid, body.regions, body.cash, body.purpose)
    return {"ok": True}
