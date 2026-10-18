"""내 자료 주소 (로그인 필요). 라우터는 서비스만 부릅니다."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from aucs_api import settings
from aucs_api.auth.user import current_user_id
from aucs_api.services import me, registry

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


class BidIn(BaseModel):
    item_id: str
    sale_date: date
    outcome: str = Field(pattern="^(won|lost|not_bid|cancelled)$")
    my_bid_krw: int | None = Field(default=None, gt=0)
    winning_bid_krw: int | None = Field(default=None, gt=0)
    second_bid_krw: int | None = Field(default=None, gt=0)
    bidder_count: int | None = Field(default=None, ge=0)
    pay_date: date | None = None
    memo: str | None = Field(default=None, max_length=200)


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


@router.get("/bids")
def get_bids(uid: Uid) -> dict[str, Any]:
    return me.bids(uid, date.today())


@router.put("/bids")
def put_bid(body: BidIn, uid: Uid) -> dict[str, bool]:
    me.bid_save(uid, body.model_dump())
    return {"ok": True}


@router.delete("/bids/{bid_id}")
def delete_bid(bid_id: int, uid: Uid) -> dict[str, bool]:
    me.bid_remove(uid, bid_id)
    return {"ok": True}


@router.get("/registries/{item_id}")
def get_registry(item_id: str, uid: Uid) -> dict[str, Any] | None:
    return registry.latest(uid, item_id)


class RightFixIn(BaseModel):
    section: str = Field(pattern="^(갑|을)$")
    rank_no: str = Field(max_length=20)
    purpose: str = Field(max_length=40)


@router.patch("/registries/{item_id}/rights")
def patch_registry_right(item_id: str, body: RightFixIn, uid: Uid) -> dict[str, Any] | None:
    try:
        return registry.fix_right(uid, item_id, body.section, body.rank_no, body.purpose)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/registries/{item_id}")
async def post_registry(
    item_id: str, uid: Uid, tasks: BackgroundTasks, file: Annotated[UploadFile, File()]
) -> dict[str, Any]:
    data = await file.read()
    if len(data) > registry.MAX_BYTES:
        raise HTTPException(413, "10MB보다 큰 파일은 올릴 수 없어요")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "PDF 파일만 올릴 수 있어요")
    upload_id = registry.save_upload(uid, item_id, file.filename or "registry.pdf", data)
    tasks.add_task(registry.parse_upload, upload_id)
    return {"upload_id": upload_id, "status": "processing"}
