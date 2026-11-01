"""내 자료 주소 (로그인 필요). 라우터는 서비스만 부릅니다."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from aucs_api import settings
from aucs_api.auth.user import current_user_id
from aucs_api.services import me, mock, registry

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


@router.get("/home")
def get_home(uid: Uid) -> dict[str, Any]:
    """홈 화면 내 자료 한 번에(관심·알림·비교함에서 뺀 물건)."""
    return me.home(uid, date.today())


@router.get("/watch/ids")
def get_watch_ids(uid: Uid) -> list[str]:
    return me.watch_ids(uid)


@router.put("/watch/{item_id}")
def put_watch(item_id: str, uid: Uid) -> dict[str, bool]:
    me.watch_add(uid, item_id)
    return {"ok": True}


class StepIn(BaseModel):
    step: str


@router.put("/watch/{item_id}/step")
def put_watch_step(item_id: str, body: StepIn, uid: Uid) -> dict[str, bool]:
    if not me.watch_set_step(uid, item_id, body.step):
        raise HTTPException(status_code=400, detail="없는 단계이거나 관심 물건이 아니에요")
    return {"ok": True}


class MemoIn(BaseModel):
    memo: str = Field(default="", max_length=2000)


class CheckIn(BaseModel):
    key: str = Field(max_length=80)
    done: bool


class CalcIn(BaseModel):
    bid_krw: int = Field(gt=0)
    cash_krw: int | None = None


def _ok(done: bool) -> dict[str, bool]:
    if not done:
        raise HTTPException(status_code=404, detail="관심 물건이 아니에요")
    return {"ok": True}


@router.get("/watch/{item_id}/workspace")
def get_workspace(item_id: str, uid: Uid) -> dict[str, Any]:
    ws = me.workspace(uid, item_id, date.today())
    if ws is None:
        raise HTTPException(status_code=404, detail="관심 물건이 아니에요")
    return ws


@router.put("/watch/{item_id}/memo")
def put_memo(item_id: str, body: MemoIn, uid: Uid) -> dict[str, bool]:
    return _ok(me.ws_memo(uid, item_id, body.memo))


@router.put("/watch/{item_id}/check")
def put_check(item_id: str, body: CheckIn, uid: Uid) -> dict[str, bool]:
    return _ok(me.ws_check(uid, item_id, body.key, body.done, date.today()))


@router.post("/watch/{item_id}/calcs")
def post_calc(item_id: str, body: CalcIn, uid: Uid) -> dict[str, bool]:
    return _ok(me.ws_calc_add(uid, item_id, body.bid_krw, body.cash_krw, date.today()))


@router.delete("/watch/{item_id}/calcs/{bid_krw}")
def delete_calc(item_id: str, bid_krw: int, uid: Uid) -> dict[str, bool]:
    return _ok(me.ws_calc_remove(uid, item_id, bid_krw))


class ExcludeIn(BaseModel):
    reason: str


@router.get("/compare")
def get_compare(uid: Uid) -> dict[str, Any]:
    return me.compare_get(uid)


@router.get("/compare/full")
def get_compare_full(
    uid: Uid, homes: Annotated[int, Query(ge=0, le=5)] = 0, first: bool = False
) -> dict[str, Any]:
    """비교함 화면 전부(담은 물건마다 상세·계산·작업 공간) 한 번에."""
    return me.compare_full(uid, homes, first, date.today())


@router.put("/compare/{item_id}")
def put_compare(item_id: str, uid: Uid) -> dict[str, bool]:
    why = me.compare_set(uid, item_id, True)
    if why == "full":
        raise HTTPException(status_code=409, detail=f"비교함은 {me.COMPARE_MAX}개까지예요")
    return _ok(why is None)


@router.delete("/compare/{item_id}")
def delete_compare(item_id: str, uid: Uid) -> dict[str, bool]:
    return _ok(me.compare_set(uid, item_id, False) is None)


@router.post("/compare/{item_id}/exclude")
def post_exclude(item_id: str, body: ExcludeIn, uid: Uid) -> dict[str, bool]:
    if not me.compare_exclude(uid, item_id, body.reason):
        raise HTTPException(status_code=400, detail="없는 이유예요")
    return {"ok": True}


@router.delete("/compare/excluded/{item_id}")
def delete_exclude(item_id: str, uid: Uid) -> dict[str, bool]:
    me.compare_unexclude(uid, item_id)
    return {"ok": True}


class MockIn(BaseModel):
    item_id: str
    decision: str = Field(pattern="^(bid|skip)$")
    bid_krw: int | None = Field(default=None, gt=0)
    max_krw: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)


@router.get("/mocks")
def get_mocks(uid: Uid) -> list[dict[str, Any]]:
    return mock.listing(uid, date.today())


@router.post("/mocks")
def post_mock(body: MockIn, uid: Uid) -> dict[str, bool]:
    mock.save(uid, body.model_dump())
    return {"ok": True}


@router.delete("/mocks/{mock_id}")
def delete_mock(mock_id: int, uid: Uid) -> dict[str, bool]:
    mock.remove(uid, mock_id)
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


class ReportIn(BaseModel):
    item_id: str = Field(max_length=80)
    section: str = Field(min_length=1, max_length=40)
    note: str = Field(min_length=1, max_length=500)


@router.post("/reports")
def post_report(body: ReportIn, uid: Uid) -> dict[str, Any]:
    """「이 값이 틀렸어요」 제보 → 관리자 검증 대기(ADM-01)."""
    return {"report_id": me.report_add(uid, body.item_id, body.section, body.note.strip())}


@router.get("/registries/{item_id}")
def get_registry(item_id: str, uid: Uid) -> dict[str, Any] | None:
    return registry.latest(uid, item_id)


class RightFixIn(BaseModel):
    section: str = Field(pattern="^(갑|을)$")
    rank_no: str = Field(max_length=20)
    purpose: str = Field(max_length=40)


@router.post("/registries/{item_id}/address-ok")
def post_registry_address_ok(item_id: str, uid: Uid) -> dict[str, Any] | None:
    return registry.accept_address(uid, item_id)


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


@router.delete("/account")
def delete_account(uid: Uid) -> dict[str, bool]:
    """회원 탈퇴 — 되돌릴 수 없음(화면에서 「탈퇴」를 직접 쳐서 확인)."""
    if not me.delete_account(uid):
        raise HTTPException(503, "지금은 탈퇴를 처리하지 못했어요 · 잠시 뒤 다시 해 주세요")
    return {"ok": True}
