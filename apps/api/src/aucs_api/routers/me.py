"""내 자료 주소 (로그인 필요). 라우터는 서비스만 부릅니다."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field

from aucs_api import settings
from aucs_api.auth.user import current_user_id
from aucs_api.services import admin_ops, billing, me, mock, points, registry


def not_limited(request: Request, authorization: str = Header(default="")) -> None:
    """관리자가 이용 제한한 회원은 저장·삭제를 못 함(읽기·탈퇴·문의는 됨, 11/2)."""
    if request.method == "GET" or request.url.path.endswith(
        ("/account", "/inquiries", "/refund", "/stop-renew")
    ):
        return
    if authorization and admin_ops.is_limited(current_user_id(authorization)):
        raise HTTPException(403, "이용이 제한된 계정이에요 · 문의로 알려 주세요")


router = APIRouter(prefix="/me", dependencies=[Depends(not_limited)])
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
    homes: int | None = None
    firstTime: bool | None = None  # noqa: N815 — 화면 저장 모양 그대로
    selling: bool | None = None


@router.get("/watch")
def get_watch(uid: Uid) -> list[dict[str, Any]]:
    return me.watch_list(uid, date.today())


def _together(**jobs: Any) -> dict[str, Any]:
    """여러 내 자료를 동시에 읽어 한 번에 돌려줌(11/3 화면마다 여러 번 부르던 것 합치기)."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(fn, *args) for k, (fn, *args) in jobs.items()}
        return {k: f.result() for k, f in futs.items()}


@router.get("/auction")
def get_auction(uid: Uid) -> dict[str, Any]:
    """「내 경매」 화면 한 번에: 관심·입찰 기록·모의입찰(예전 3번)."""
    today = date.today()
    return _together(
        watch=(me.watch_list, uid, today),
        bids=(me.bids, uid, today),
        mocks=(mock.listing, uid, today),
    )


@router.get("/more")
def get_more(uid: Uid) -> dict[str, Any]:
    """「내 정보」 화면 한 번에: 알림 조건·문의(예전 2번)."""
    return _together(searches=(me.searches, uid), inquiries=(admin_ops.my_inquiries, uid))


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


@router.get("/watch/{item_id}/panel")
def get_watch_panel(item_id: str, uid: Uid) -> dict[str, Any]:
    """관심 물건 한 칸(PC 관심 오른쪽·현장 확인) 한 번에: 물건 상세 + 내 작업 공간(11/3 — 예전 2번)."""
    from aucs_api.services import item_detail, onbid_detail

    today = date.today()
    detail = onbid_detail.detail if item_id.startswith("OB-") else item_detail.detail
    out = _together(d=(detail, item_id, today), w=(me.workspace, uid, item_id, today))
    if out["w"] is None:
        raise HTTPException(status_code=404, detail="관심 물건이 아니에요")
    return out


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


@router.get("/profile")
def get_profile(uid: Uid) -> dict[str, Any] | None:
    """계정에 저장한 내 조건(새 기기에서 되살림, 11/8)."""
    return me.load_profile(uid)


@router.put("/profile")
def put_profile(body: ProfileIn, uid: Uid) -> dict[str, Any]:
    return {"ok": True, "at": me.save_profile(uid, body.model_dump())}


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
    return _registry_saved(uid, item_id, file.filename or "registry.pdf", data, tasks)


def _registry_saved(
    uid: str, item_id: str, name: str, data: bytes, tasks: BackgroundTasks
) -> dict[str, Any]:
    """저장하고 읽기 시작. Vercel 에서는 글자 PDF 를 바로 읽고(응답 뒤 함수가 멈출 수 있어 뒤로 미루지 않음),
    그림 PDF 는 PC 가 마저 읽음. PC(개발)에서는 예전처럼 뒤에서 글자 인식까지."""
    upload_id = registry.save_upload(uid, item_id, name, data)
    if settings.ON_VERCEL:
        registry.parse_upload(upload_id, ocr=False)
    else:
        tasks.add_task(registry.parse_upload, upload_id)
    return {"upload_id": upload_id, "status": "processing"}


class FromStorageIn(BaseModel):
    path: str = Field(min_length=3, max_length=200)
    file_name: str = Field(default="registry.pdf", max_length=120)


@router.post("/registries/{item_id}/from-storage")
def post_registry_from_storage(
    item_id: str, uid: Uid, tasks: BackgroundTasks, body: FromStorageIn
) -> dict[str, Any]:
    """화면이 파일 보관함(registry-uploads/<회원>/…)에 바로 올린 등기부(11/3 — 큰 PDF 도 Vercel 에서 받게)."""
    data = registry.take_from_storage(uid, body.path)
    if data is None:
        raise HTTPException(404, "올린 파일을 찾지 못했어요 · 다시 올려 주세요")
    if len(data) > registry.MAX_BYTES:
        raise HTTPException(413, "10MB보다 큰 파일은 올릴 수 없어요")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "PDF 파일만 올릴 수 있어요")
    return _registry_saved(uid, item_id, body.file_name, data, tasks)


# 포인트 벌기(11/12, docs/design/11-points.md)
@router.get("/points")
def get_points(uid: Uid) -> dict[str, Any]:
    return points.summary(uid)


@router.get("/points/board")
def get_points_board(
    uid: Uid,
    offset: int = Query(default=0, ge=0, le=20000),
    item: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    return points.board(uid, offset, item)


@router.post("/points/hold/{item_id}/{kind}")
def post_points_hold(
    item_id: str,
    kind: Literal["registry", "appraisal"],
    uid: Uid,
    extend: bool = Query(default=False),
) -> dict[str, Any]:
    r = points.hold(uid, item_id, kind, extend)
    if r is None:
        raise HTTPException(409, "다른 분이 먼저 맡았어요" if not extend else "더 늘릴 수 없어요")
    return r


class AppraisalIn(BaseModel):
    path: str = Field(min_length=3, max_length=200)


@router.post("/appraisals/{item_id}/from-storage")
def post_appraisal_from_storage(item_id: str, uid: Uid, body: AppraisalIn) -> dict[str, Any]:
    """화면이 보관함(appraisal-uploads/<회원>/…)에 바로 올린 감정평가서 — 맞으면 원본 보관 + 포인트."""
    return points.save_appraisal(uid, item_id, body.path)


@router.get("/academy")
def get_academy(uid: Uid) -> dict[str, Any]:
    """옥스아카데미: 포인트를 받은 단계들 · 계정에 적어 둔 진도(들은 수업 · 해 본 과제)."""
    return {"stages": points.academy_done(uid), "done": points.academy_progress(uid)}


class AcademyIn(BaseModel):
    keys: list[str] = Field(max_length=200)


@router.put("/academy")
def put_academy(uid: Uid, body: AcademyIn) -> dict[str, int]:
    """들은 수업 · 해 본 과제를 계정에 적음(11/14 — 다른 기기에서도 이어지게)."""
    return {"added": points.academy_mark(uid, body.keys)}


@router.post("/academy/{stage}")
def post_academy(stage: str, uid: Uid) -> dict[str, Any]:
    """한 단계를 다 들었어요 — 포인트는 단계마다 한 번."""
    return points.academy_grant(uid, stage[:20])


@router.get("/appraisals/{item_id}")
def get_my_appraisal(item_id: str, uid: Uid) -> dict[str, Any]:
    """이 물건에 내가 올린 감정평가서가 어떻게 됐는지(없으면 빈 것, 11/14)."""
    return points.my_appraisal(uid, item_id) or {}


@router.delete("/account")
def delete_account(uid: Uid) -> dict[str, bool]:
    """회원 탈퇴 — 되돌릴 수 없음(화면에서 「탈퇴」를 직접 쳐서 확인)."""
    if not me.delete_account(uid):
        raise HTTPException(503, "지금은 탈퇴를 처리하지 못했어요 · 잠시 뒤 다시 해 주세요")
    return {"ok": True}


class AskIn(BaseModel):
    body: str = Field(min_length=2, max_length=2000)


@router.get("/inquiries")
def get_inquiries(uid: Uid) -> list[dict[str, Any]]:
    return admin_ops.my_inquiries(uid)


@router.post("/inquiries")
def post_inquiry(uid: Uid, body: AskIn) -> dict[str, int]:
    return {"inquiry_id": admin_ops.ask(uid, body.body)}


# 이용권·결제(11/3)
@router.get("/billing")
def get_billing(uid: Uid) -> dict[str, Any]:
    return billing.my_billing(uid)


class RefundIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/billing/{payment_id}/refund")
def post_refund(uid: Uid, payment_id: int, body: RefundIn) -> dict[str, Any]:
    r = billing.request_refund(uid, payment_id, body.reason)
    if r is None:
        raise HTTPException(404, "환불할 수 있는 결제가 아니에요")
    return r


@router.post("/billing/{payment_id}/stop-renew")
def post_stop_renew(uid: Uid, payment_id: int) -> dict[str, bool]:
    if not billing.stop_renew(uid, payment_id):
        raise HTTPException(404, "없는 결제")
    return {"ok": True}
