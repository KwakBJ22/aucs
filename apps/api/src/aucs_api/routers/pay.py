"""결제 주소(11/23 미리 구성 — 토스페이먼츠 키를 넣으면 열림). 라우터는 서비스만 부릅니다.

/pay/webhook 은 로그인 없이(결제가 열렸는지는 quote 의 open), /me/pay/* 는 로그인해서.
웹훅 주소(토스 개발자센터에 등록): https://api.aucs.co.kr/pay/webhook
"""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from aucs_api.auth.user import current_user_id
from aucs_api.services import pay

public = APIRouter(prefix="/pay")
router = APIRouter(prefix="/me/pay")
Uid = Annotated[str, Depends(current_user_id)]
Plan = Literal["personal", "one", "points"]
Period = Literal["month", "year", "one"]


class OrderIn(BaseModel):
    plan: Plan
    period: Period
    item_id: str | None = Field(default=None, max_length=80)
    method: str = Field(max_length=20)
    # 포인트 충전 금액(11/26) — 서버가 고른 값 중 하나인지 봄
    amount_krw: int | None = Field(default=None, gt=0)


class ConfirmIn(BaseModel):
    payment_key: str = Field(min_length=1, max_length=200)
    order_id: str = Field(min_length=6, max_length=64)
    amount: int = Field(gt=0)


class FailIn(BaseModel):
    order_id: str = Field(min_length=6, max_length=64)
    code: str = Field(default="", max_length=60)
    message: str = Field(default="", max_length=300)


class CardIn(BaseModel):
    auth_key: str = Field(min_length=1, max_length=300)
    customer_key: str = Field(min_length=22, max_length=60)


@public.post("/webhook")
async def post_webhook(request: Request) -> dict[str, Any]:
    """토스 웹훅 — 본문은 믿지 않고 결제를 다시 조회해 반영(pay.webhook). 늘 200 으로 답함(다시 보내기 막기)."""
    try:
        body = json.loads(await request.body() or b"{}")
    except ValueError:
        return {"ok": False}
    return pay.webhook(body if isinstance(body, dict) else {})


@router.get("/quote")
def get_quote(uid: Uid, plan: Plan, period: Period, item: str | None = None) -> dict[str, Any]:
    return pay.quote(uid, plan, period, item)


@router.post("/order")
def post_order(uid: Uid, body: OrderIn) -> dict[str, Any]:
    return pay.make_order(uid, body.plan, body.period, body.item_id, body.method, body.amount_krw)


@router.post("/confirm")
def post_confirm(uid: Uid, body: ConfirmIn) -> dict[str, Any]:
    return pay.confirm(uid, body.payment_key, body.order_id, body.amount)


@router.post("/fail")
def post_fail(uid: Uid, body: FailIn) -> dict[str, bool]:
    pay.fail(uid, body.order_id, body.code, body.message)
    return {"ok": True}


@router.get("/order/{order_id}")
def get_order(uid: Uid, order_id: str) -> dict[str, Any]:
    return pay.order_status(uid, order_id)


@router.post("/card/start")
def post_card_start(uid: Uid) -> dict[str, Any]:
    return pay.card_start(uid)


@router.post("/card/issue")
def post_card_issue(uid: Uid, body: CardIn) -> dict[str, Any]:
    return pay.card_issue(uid, body.auth_key, body.customer_key)
