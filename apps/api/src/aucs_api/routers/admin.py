"""관리자 주소 (11/2 관리자 모드 1단계). 라우터는 서비스만 부릅니다.

들어오기: 로그인 + app.admins + 2단계 인증. 역할: viewer(보기) < operator(운영) < owner(대표).
"""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from aucs_api.auth.admin import Admin, admin_login, require_admin, require_role
from aucs_api.db import connect
from aucs_api.services import admin, admin_money, admin_ops, billing, points

router = APIRouter(prefix="/admin")
Any_ = Annotated[Admin, Depends(require_admin)]
Op = Annotated[Admin, Depends(require_role("operator"))]
Owner = Annotated[Admin, Depends(require_role("owner"))]


def _together(**jobs: Any) -> dict[str, Any]:
    """메뉴 한 화면에 필요한 것을 동시에 읽어 한 번에(11/3 — 예전엔 메뉴마다 2~5번)."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(fn, *args) for k, (fn, *args) in jobs.items()}
        return {k: f.result() for k, f in futs.items()}


@router.get("/screen/{menu}")
def get_screen(
    a: Any_,
    menu: str,
    q: str = Query(default="", max_length=60),
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """관리자 메뉴 한 화면 자료 한 번에. menu: jobs · review · members · stats · settings."""
    if menu == "jobs":
        return _together(jobs=(admin_ops.jobs,), errors=(admin_ops.errors,))
    if menu == "review":
        return _together(review=(admin_ops.review,), hidden=(admin_ops.hidden_items,))
    if menu == "members":
        out = _together(users=(admin_ops.users, q), inquiries=(admin_ops.inquiries, True),
                        refunds=(billing.refund_requests, True))  # fmt: skip
        for r in out["refunds"]:
            r["email"] = admin_ops.mask(r["email"])
        return out
    if menu == "plans":
        return admin_money.screen()
    if menu == "stats":
        return _together(status=(admin.status,), stats=(admin_ops.stats, days))
    if menu == "settings":
        jobs: dict[str, Any] = {"rules": (admin_ops.rule_tables,), "flags": (admin.flags,),
                                "dongs": (admin_ops.dong_alias,), "admins": (admin_ops.admins,)}  # fmt: skip
        if a.role == "owner":
            jobs["audit"] = (admin_ops.audit_log,)
        out = _together(**jobs)
        out.setdefault("audit", [])
        return out
    raise HTTPException(404, "없는 메뉴")


@router.get("/me")
def get_me(a: Annotated[Admin, Depends(admin_login)]) -> dict[str, Any]:
    """관리자인지·역할·2단계 인증 했는지(화면이 맨 먼저 부름)."""
    return {"role": a.role, "mfa": a.mfa}


# 1 오늘
@router.get("/today")
def get_today(_: Any_) -> dict[str, Any]:
    return admin_ops.today()


@router.get("/status")
def get_status(_: Any_) -> dict[str, Any]:
    return admin.status()


@router.get("/stats")
def get_stats(_: Any_, days: int = Query(default=30, ge=1, le=365)) -> dict[str, Any]:
    return admin_ops.stats(days)


# 2 작업·수집
@router.get("/jobs")
def get_jobs(_: Any_) -> dict[str, Any]:
    return admin_ops.jobs()


@router.post("/jobs/mark-stale")
def post_mark_stale(a: Op) -> dict[str, int]:
    return {"n": admin_ops.mark_stale(a.user_id)}


class JobReqIn(BaseModel):
    job_key: str = Field(min_length=2, max_length=120)


@router.post("/job-requests")
def post_job_request(a: Op, body: JobReqIn) -> dict[str, Any]:
    r = admin_ops.request_job(a.user_id, body.job_key)
    if r is None:
        raise HTTPException(400, "요청할 수 없는 작업이에요")
    return r


@router.get("/errors")
def get_errors(_: Any_) -> list[dict[str, Any]]:
    return admin_ops.errors()


class ErrFixIn(BaseModel):
    side: str
    message: str


@router.post("/errors/fixed")
def post_error_fixed(a: Op, body: ErrFixIn) -> dict[str, bool]:
    admin_ops.error_fixed(a.user_id, body.side, body.message)
    return {"ok": True}


# 3 자료 검수
@router.get("/review")
def get_review(_: Any_) -> dict[str, Any]:
    return admin_ops.review()


class ReportIn(BaseModel):
    status: Literal["fixed", "rejected"]


@router.put("/reports/{report_id}")
def put_report(a: Op, report_id: int, body: ReportIn) -> dict[str, bool]:
    if not admin.close_report(report_id, body.status):
        raise HTTPException(404, "없거나 이미 처리한 제보")
    with connect() as c:
        admin_ops.audit(c, a.user_id, "report_close", str(report_id), None, {"status": body.status})
    return {"ok": True}


class FieldIn(BaseModel):
    value: Any | None = None  # 없으면 「맞음」


@router.put("/fields/{field_id}")
def put_field(a: Op, field_id: int, body: FieldIn) -> dict[str, bool]:
    if not admin_ops.check_field(a.user_id, field_id, body.value):
        raise HTTPException(404, "없는 칸")
    return {"ok": True}


class SignalIn(BaseModel):
    item_id: str
    rule_id: str
    status: Literal["확정", "없음"]


@router.put("/signals")
def put_signal(a: Op, body: SignalIn) -> dict[str, bool]:
    if not admin_ops.decide_signal(a.user_id, body.item_id, body.rule_id, body.status):
        raise HTTPException(404, "없는 신호")
    return {"ok": True}


class HideIn(BaseModel):
    hidden: bool
    reason: str | None = Field(default=None, max_length=200)


@router.put("/items/{item_id}/hide")
def put_hide(a: Op, item_id: str, body: HideIn) -> dict[str, bool]:
    if not admin_ops.hide_item(a.user_id, item_id, body.hidden, body.reason):
        raise HTTPException(404, "없는 물건")
    return {"ok": True}


@router.get("/items/hidden")
def get_hidden(_: Any_) -> list[dict[str, Any]]:
    return admin_ops.hidden_items()


# 4 회원
@router.get("/users")
def get_users(_: Any_, q: str = Query(default="", max_length=60)) -> list[dict[str, Any]]:
    return admin_ops.users(q)


@router.get("/users/{uid}")
def get_user(_: Any_, uid: str) -> dict[str, Any]:
    u = admin_ops.user_detail(uid)
    if not u:
        raise HTTPException(404, "없는 회원")
    return u


@router.post("/users/{uid}/email")
def post_reveal_email(a: Owner, uid: str) -> dict[str, str]:
    e = admin_ops.reveal_email(a.user_id, uid)
    if not e:
        raise HTTPException(404, "없는 회원")
    return {"email": e}


class GrantIn(BaseModel):
    plan: Literal["basic", "pro"]
    days: int = Field(ge=1, le=366)
    reason: str = Field(min_length=2, max_length=200)


@router.post("/users/{uid}/grants")
def post_grant(a: Op, uid: str, body: GrantIn) -> dict[str, Any]:
    r = admin_ops.grant(a.user_id, uid, body.plan, body.days, body.reason)
    if not r:
        raise HTTPException(404, "없는 회원")
    return r


class PointsIn(BaseModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=2, max_length=200)


@router.post("/users/{uid}/points")
def post_points(a: Owner, uid: str, body: PointsIn) -> dict[str, Any]:
    """포인트 더하기·빼기(돈과 같아 대표만, 11/12)."""
    if body.delta == 0:
        raise HTTPException(400, "0 은 바꿀 것이 없어요")
    r = admin_money.adjust_points(a.user_id, uid, body.delta, body.reason)
    if not r:
        raise HTTPException(404, "없는 회원")
    return r


class LimitIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)  # 없으면 풀기


@router.put("/users/{uid}/limit")
def put_limit(a: Owner, uid: str, body: LimitIn) -> dict[str, bool]:
    if not admin_ops.set_limit(a.user_id, uid, body.reason):
        raise HTTPException(404, "없는 회원")
    return {"ok": True}


@router.get("/inquiries")
def get_inquiries(_: Any_, all_: bool = Query(default=False, alias="all")) -> list[dict[str, Any]]:
    return admin_ops.inquiries(only_open=not all_)


class AnswerIn(BaseModel):
    answer: str = Field(min_length=2, max_length=2000)


@router.put("/inquiries/{inquiry_id}")
def put_answer(a: Op, inquiry_id: int, body: AnswerIn) -> dict[str, bool]:
    if not admin_ops.answer(a.user_id, inquiry_id, body.answer):
        raise HTTPException(404, "없는 문의")
    return {"ok": True}


# 5 이용권·결제: 환불 요청(11/3)
@router.get("/refunds")
def get_refunds(_: Any_, all_: bool = Query(default=False, alias="all")) -> list[dict[str, Any]]:
    rows = billing.refund_requests(only_waiting=not all_)
    for r in rows:
        r["email"] = admin_ops.mask(r["email"])
    return rows


class RefundDecideIn(BaseModel):
    ok: bool
    amount_krw: int | None = Field(default=None, ge=0)
    answer: str = Field(min_length=2, max_length=300)


@router.put("/refunds/{request_id}")
def put_refund(a: Owner, request_id: int, body: RefundDecideIn) -> dict[str, bool]:
    if not billing.decide_refund(a.user_id, request_id, body.ok, body.amount_krw, body.answer):
        raise HTTPException(404, "없거나 이미 처리한 요청")
    return {"ok": True}


# 5-2 포인트 벌기: 글 없는 그림 감정평가서 확인(11/12)
@router.get("/points/review")
def get_points_review(_: Any_) -> list[dict[str, Any]]:
    return points.review_list()


@router.get("/points/review/{contrib_id}/pdf")
def get_points_review_pdf(_: Any_, contrib_id: int) -> Response:
    data = points.review_pdf(contrib_id)
    if data is None:
        raise HTTPException(404, "원본이 없어요")
    return Response(data, media_type="application/pdf")


class PointsDecideIn(BaseModel):
    ok: bool


@router.put("/points/review/{contrib_id}")
def put_points_review(_: Op, contrib_id: int, body: PointsDecideIn) -> dict[str, bool]:
    if not points.review_decide(contrib_id, body.ok):
        raise HTTPException(404, "없거나 이미 처리했어요")
    return {"ok": True}


# 6 공지
@router.get("/notices")
def get_notices(_: Any_) -> list[dict[str, Any]]:
    return admin_ops.notices(active_only=False)


class NoticeIn(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    body: str = Field(default="", max_length=2000)
    start_at: str | None = None
    end_at: str | None = None
    pinned: bool = False


@router.post("/notices")
def post_notice(a: Op, body: NoticeIn) -> dict[str, Any]:
    return admin_ops.save_notice(a.user_id, None, body.model_dump()) or {}


@router.put("/notices/{nid}")
def put_notice(a: Op, nid: int, body: NoticeIn) -> dict[str, Any]:
    r = admin_ops.save_notice(a.user_id, nid, body.model_dump())
    if not r:
        raise HTTPException(404, "없는 공지")
    return r


@router.post("/notices/{nid}/end")
def post_notice_end(a: Op, nid: int) -> dict[str, bool]:
    if not admin_ops.end_notice(a.user_id, nid):
        raise HTTPException(404, "없는 공지")
    return {"ok": True}


# 8 설정
@router.get("/flags")
def get_flags(_: Any_) -> list[dict[str, Any]]:
    return admin.flags()


class FlagIn(BaseModel):
    enabled: bool


@router.put("/flags/{key}")
def put_flag(a: Owner, key: str, body: FlagIn) -> dict[str, Any]:
    row = admin_ops.set_flag(a.user_id, key, body.enabled)
    if row is None:
        raise HTTPException(404, "없는 설정")
    return row


@router.get("/rule-tables")
def get_rule_tables(_: Any_) -> list[dict[str, Any]]:
    return admin_ops.rule_tables()


class RuleIn(BaseModel):
    valid_from: date
    value: Any
    basis: str = Field(min_length=2, max_length=300)


@router.post("/rule-tables/{key}")
def post_rule(a: Owner, key: str, body: RuleIn) -> dict[str, bool]:
    if not admin_ops.new_rule_version(a.user_id, key, body.valid_from, body.value, body.basis):
        raise HTTPException(400, "지난 버전보다 늦은 적용일을 넣어 주세요")
    return {"ok": True}


@router.post("/rule-tables/{key}/{valid_from}/reviewed")
def post_rule_reviewed(a: Owner, key: str, valid_from: date) -> dict[str, bool]:
    if not admin_ops.rule_reviewed(a.user_id, key, valid_from):
        raise HTTPException(404, "없는 기준표")
    return {"ok": True}


@router.get("/dong-alias")
def get_dong_alias(_: Any_) -> list[dict[str, Any]]:
    return admin_ops.dong_alias()


class DongIn(BaseModel):
    sido: str = Field(min_length=2, max_length=20)
    city: str = Field(min_length=1, max_length=30)
    old_name: str = Field(min_length=1, max_length=30)
    new_name: str = Field(min_length=1, max_length=30)
    changed_on: date | None = None


@router.post("/dong-alias")
def post_dong_alias(a: Op, body: DongIn) -> dict[str, bool]:
    admin_ops.add_dong_alias(a.user_id, body.model_dump())
    return {"ok": True}


@router.get("/admins")
def get_admins(_: Any_) -> list[dict[str, Any]]:
    return admin_ops.admins()


class AdminIn(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    role: Literal["owner", "operator", "viewer"]


@router.post("/admins")
def post_admin(a: Owner, body: AdminIn) -> dict[str, str]:
    uid = admin_ops.add_admin(a.user_id, body.email, body.role)
    if not uid:
        raise HTTPException(404, "옥스에 가입한 이메일이 아니에요")
    return {"user_id": uid}


@router.delete("/admins/{uid}")
def delete_admin(a: Owner, uid: str) -> dict[str, bool]:
    r = admin_ops.remove_admin(a.user_id, uid)
    if r == "last_owner":
        raise HTTPException(400, "대표가 한 명뿐이라 뺄 수 없어요")
    if r == "none":
        raise HTTPException(404, "관리자가 아니에요")
    return {"ok": True}


@router.get("/audit")
def get_audit(_: Owner) -> list[dict[str, Any]]:
    return admin_ops.audit_log()


# 회원 쪽: 공지 보기(공개)
public = APIRouter()


@public.get("/plans/prices")
def get_prices() -> dict[str, Any]:
    """이용권 화면 가격(기준표 plans — 관리자가 바꾸면 적용일부터)."""
    return billing.prices()


@public.get("/notices")
def get_public_notices() -> list[dict[str, Any]]:
    return admin_ops.notices(active_only=True)
