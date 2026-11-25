"""결제 전 · 후(11/23 대표님 「결제 붙이면 돌아가게 전 · 후를 미리」) — 토스페이먼츠.

흐름
  결제 전: 화면이 quote(값 · 기간 보기) → order(서버가 금액을 정해 주문을 만듦) → 토스 결제창
  결제 후: 토스가 화면으로 돌려보냄(paymentKey · orderId · amount) → confirm(금액을 우리 주문과 맞춰 보고 승인)
           → app.payments 한 줄(이용권이 열림) · 알림. 입금 전용 계좌는 입금되면 웹훅으로 같은 일.
  매달: 카드 등록(빌링키) → 첫 달 바로 결제 → 매일 새벽 cron 이 끝나는 날 다음 달을 결제(실패 3번이면 멈추고 알림).
  환불: 관리자가 환불을 승인하면 billing.decide_refund 가 cancel() 로 카드 결제를 취소.

키(settings.TOSS_CLIENT_KEY · TOSS_SECRET_KEY)가 없으면 is_open() 이 거짓 → 주소들이 503, 화면은 단추를 잠금.
금액 · 기간은 늘 서버가 정함(화면 값은 믿지 않음). 토스 응답은 다시 조회해 확인(웹훅 본문만 믿지 않음).
"""

import base64
import secrets
from datetime import date, timedelta
from typing import Any

import httpx
from fastapi import HTTPException

from aucs_api import settings
from aucs_api.db import connect
from aucs_api.services import billing

API = "https://api.tosspayments.com"
PLAN_NAME = {"personal": "개인", "pro": "전문가", "one": "한 건"}
PERIOD_NAME = {"month": "매달", "year": "1년", "one": "한 건"}
# 화면에서 고르는 수단(copy.checkout.methods 의 열쇠) — 매달은 카드 자동결제(billing)만
METHODS = {"card", "bank", "vbank", "toss", "naver", "kakao"}
RENEW_TRIES = 3
# 포인트 충전(11/26 대표님): 고를 수 있는 금액(1원 = 1P) · 충전한 포인트 유효기간(5년)
CHARGE_KRW = (5_000, 10_000, 30_000, 50_000)
CHARGE_EXPIRE_DAYS = 365 * 5


def is_open() -> bool:
    return bool(settings.TOSS_CLIENT_KEY and settings.TOSS_SECRET_KEY)


def _need_open() -> None:
    if not is_open():
        raise HTTPException(503, "결제는 사업자등록과 결제 계약이 끝나면 열려요")


# ---------- 순수 계산(시험 있음) ----------


def add_months(d: date, n: int) -> date:
    """같은 날 n달 뒤(그 달에 그날이 없으면 그 달 마지막 날)."""
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def period_end(period: str, start: date, sale_date: date | None = None) -> date:
    """이용권 마지막 날(그날까지 열림). 매달 = 한 달 뒤 전날 · 1년 = 1년 뒤 전날 · 한 건 = 매각기일 다음 날."""
    if period == "month":
        return add_months(start, 1) - timedelta(days=1)
    if period == "year":
        return add_months(start, 12) - timedelta(days=1)
    if sale_date is None:
        raise ValueError("한 건 이용권은 매각기일이 있어야 해요")
    return sale_date + timedelta(days=1)


def new_order_id(today: date) -> str:
    """토스 orderId: 6~64자 · 영문 · 숫자 · - _ = 만. 날짜 + 무작위."""
    return f"aucs-{today:%Y%m%d}-{secrets.token_urlsafe(12)}"


def order_name(plan: str, period: str, title: str | None = None) -> str:
    if plan == "points":
        return f"옥스경매 포인트 충전 · {title}"
    base = f"옥스경매 {PLAN_NAME[plan]}" + ("" if plan == "one" else f" · {PERIOD_NAME[period]}")
    return (f"{base} · {title}" if title else base)[:100]


def method_note(toss: dict[str, Any]) -> str:
    """결제 내역에 보일 수단 한 줄(토스 응답의 method · 간편결제 이름)."""
    m = str(toss.get("method") or "")
    ep = (toss.get("easyPay") or {}).get("provider")
    return f"{m} · {ep}" if ep and ep != m else (m or "토스페이먼츠")


# ---------- 토스 부르기 ----------


def _auth() -> str:
    raw = f"{settings.TOSS_SECRET_KEY}:".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _toss(method: str, path: str, body: dict[str, Any] | None = None, idem: str | None = None) -> dict[str, Any]:  # fmt: skip
    """토스 API. 실패하면 HTTPException(402, 토스 메시지) — 코드는 detail 앞에 [코드]."""
    headers = {"Authorization": _auth()}
    if idem:
        headers["Idempotency-Key"] = idem
    try:
        r = httpx.request(method, API + path, json=body, headers=headers, timeout=65)
    except httpx.HTTPError as e:
        raise HTTPException(502, "결제 회사와 연결이 끊겼어요 · 잠시 뒤 다시 해 주세요") from e
    data = r.json() if r.content else {}
    if r.status_code >= 400:
        code = str(data.get("code") or r.status_code)
        msg = str(data.get("message") or "결제를 마치지 못했어요")
        raise HTTPException(402, f"[{code}] {msg}")
    return data


def payment(payment_key: str) -> dict[str, Any]:
    return _toss("GET", f"/v1/payments/{payment_key}")


def cancel(payment_key: str, reason: str, amount: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"cancelReason": reason[:200] or "환불"}
    if amount is not None:
        body["cancelAmount"] = amount
    return _toss(
        "POST", f"/v1/payments/{payment_key}/cancel", body, idem=f"cancel-{payment_key}-{amount}"
    )


# ---------- 결제 전 ----------


def _item(c: Any, item_id: str, check: bool = True) -> dict[str, Any]:
    """한 건 이용권 물건: 사건번호 · 주소 · 매각기일(공매는 입찰 마감일). 지난 물건이면 막음(check)."""
    r = c.execute(
        """select i.item_id, c.case_no as no, i.address, i.sale_date as until_day
           from core.items i join core.cases c using (case_id) where i.item_id = %s
           union all
           select o.item_id, o.item_id, coalesce(o.title, o.address), (o.bid_end at time zone 'Asia/Seoul')::date
           from core.onbid_items o where o.item_id = %s""",
        (item_id, item_id),
    ).fetchone()
    if not r:
        raise HTTPException(404, "물건을 찾지 못했어요")
    if check and (not r["until_day"] or r["until_day"] < date.today()):
        raise HTTPException(409, "매각기일이 지났거나 정해지지 않은 물건이에요")
    return r


def _amount(plan: str, period: str) -> int:
    p = billing.prices().get(plan) or {}
    v = (p.get("one") or p.get("month")) if plan == "one" else p.get(period)
    if not v:
        raise HTTPException(409, "아직 팔지 않는 이용권이에요")
    return int(v)


def _check(plan: str, period: str) -> None:
    ok = (plan == "personal" and period in ("month", "year")) or (
        plan in ("one", "points") and period == "one"
    )
    if not ok:  # 전문가 이용권은 아직 안 팖(이용권 화면 「준비 중」)
        raise HTTPException(409, "아직 팔지 않는 이용권이에요")


def quote(uid: str, plan: str, period: str, item_id: str | None) -> dict[str, Any]:
    """결제 화면에 보일 값(키가 없어도 보여 줌 — 단추만 잠김). 한 건은 상세가 잠겨 있어도 여기서 물건 이름을 줌."""
    _check(plan, period)
    today = date.today()
    item = None
    with connect() as c:
        if plan == "one":
            if not item_id:
                raise HTTPException(400, "물건을 골라 주세요")
            item = _item(c, item_id)
        card = c.execute("select card_label from app.billing_cards where user_id = %s and billing_key is not null", (uid,)).fetchone()  # fmt: skip
    return {
        "open": is_open(),
        "amount_krw": _amount(plan, period),
        "until": period_end(period, today, item["until_day"] if item else None),
        "item": {"id": item["item_id"], "no": item["no"], "address": item["address"]}
        if item
        else None,
        "card": card["card_label"] if card else None,
    }


def make_order(
    uid: str,
    plan: str,
    period: str,
    item_id: str | None,
    method: str,
    charge_krw: int | None = None,
) -> dict[str, Any]:
    """결제창을 열기 전 주문. 금액 · 이름은 서버가 정하고 화면은 이 값 그대로 결제창에 넘김."""
    _need_open()
    _check(plan, period)
    if plan == "points" and charge_krw not in CHARGE_KRW:
        raise HTTPException(400, "충전할 금액을 골라 주세요")
    if period == "month" or method not in METHODS:
        raise HTTPException(
            400, "매달은 카드 등록으로 결제해요" if period == "month" else "결제 수단을 골라 주세요"
        )
    today = date.today()
    with connect() as c:
        title = None
        if plan == "one":
            if not item_id:
                raise HTTPException(400, "물건을 골라 주세요")
            it = _item(c, item_id)
            title = it["no"]
            mine = c.execute(
                """select 1 from app.payments where user_id = %s and item_id = %s and plan = 'one'
                   and status in ('paid','part_refunded') and valid_to >= current_date""",
                (uid, item_id),
            ).fetchone()
            if mine:
                raise HTTPException(409, "이미 이 물건 이용권이 있어요")
        oid = new_order_id(today)
        if plan == "points":
            amount = int(charge_krw or 0)
            name = order_name(plan, period, f"{amount:,}P")
        else:
            name = order_name(plan, period, title)
            amount = _amount(plan, period)
        c.execute(
            """insert into app.pay_orders (order_id, user_id, plan, period, item_id, amount_krw, order_name, method)
               values (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (oid, uid, plan, period, item_id if plan == "one" else None, amount, name, method),
        )
        email = c.execute("select email from auth.users where id = %s", (uid,)).fetchone()
    return {
        "order_id": oid,
        "amount_krw": amount,
        "order_name": name,
        "client_key": settings.TOSS_CLIENT_KEY,
        "customer_key": _customer_key(uid),
        "email": email["email"] if email else None,
    }


def _customer_key(uid: str) -> str:
    """회원마다 하나(무작위 — 회원 id 를 그대로 쓰지 않음, 토스 권고)."""
    with connect() as c:
        r = c.execute(
            "select customer_key from app.billing_cards where user_id = %s", (uid,)
        ).fetchone()
        if r:
            return str(r["customer_key"])
        key = "aucs_" + secrets.token_urlsafe(24)
        c.execute(
            "insert into app.billing_cards (user_id, customer_key) values (%s,%s) on conflict (user_id) do nothing",
            (uid, key),
        )
        r = c.execute(
            "select customer_key from app.billing_cards where user_id = %s", (uid,)
        ).fetchone()
    return str(r["customer_key"])


# ---------- 결제 후 ----------


# 주문에서 읽는 칸(select * 쓰지 않음 — 공통 지침 2-5)
_O = "order_id, user_id, plan, period, item_id, amount_krw, order_name, status, payment_key, deposit_secret, vbank, fail_msg, payment_id"


def _result(o: dict[str, Any]) -> dict[str, Any]:
    """화면에 돌려줄 주문 결과(완료 · 입금 기다림 · 실패)."""
    out: dict[str, Any] = {
        "order_id": o["order_id"], "status": o["status"], "plan": o["plan"], "period": o["period"],
        "item_id": o["item_id"], "amount_krw": o["amount_krw"], "order_name": o["order_name"],
        "vbank": o.get("vbank"), "fail": o.get("fail_msg"),
    }  # fmt: skip
    if o.get("payment_id"):
        with connect() as c:
            p = c.execute("select valid_to, receipt_url from app.payments where payment_id = %s", (o["payment_id"],)).fetchone()  # fmt: skip
        if p:
            out["until"] = p["valid_to"]
            out["receipt_url"] = p["receipt_url"]
    return out


def _grant(order_id: str, toss: dict[str, Any], auto_renew: bool = False, start: date | None = None) -> dict[str, Any]:  # fmt: skip
    """승인된 결제 → 이용권 한 줄. 두 번 불려도 한 번만(주문에 payment_id 가 있으면 그대로)."""
    with connect() as c:
        o = c.execute(
            "select " + _O + " from app.pay_orders where order_id = %s for update", (order_id,)
        ).fetchone()
        if not o:
            raise HTTPException(404, "주문을 찾지 못했어요")
        if o["payment_id"] or o["status"] == "paid":
            return dict(o)
        if int(toss.get("totalAmount") or 0) != int(o["amount_krw"]):
            # 금액이 다르면 이용권을 열지 않음(관리자 오류 목록에 남도록 500)
            raise RuntimeError(
                f"결제 금액 불일치 {order_id}: {toss.get('totalAmount')} != {o['amount_krw']}"
            )
        if o["plan"] == "points":
            return _charge_points(c, o, toss)
        begin = start or date.today()
        sale = _item(c, o["item_id"], check=False)["until_day"] if o["plan"] == "one" else None
        until = period_end(o["period"], begin, sale or begin)
        pay = c.execute(
            """insert into app.payments (user_id, plan, period, amount_krw, item_id, status, auto_renew, method_note,
                   order_id, receipt_url, valid_from, valid_to, payment_key)
               values (%s,%s,%s,%s,%s,'paid',%s,%s,%s,%s,%s,%s,%s) returning payment_id""",
            (o["user_id"], o["plan"], o["period"], o["amount_krw"], o["item_id"], auto_renew, method_note(toss),
             order_id, (toss.get("receipt") or {}).get("url"), begin, until, toss.get("paymentKey")),
        ).fetchone()  # fmt: skip
        o = c.execute(
            """update app.pay_orders set status = 'paid', payment_key = %s, payment_id = %s, done_at = now()
               where order_id = %s returning """
            + _O,
            (toss.get("paymentKey"), pay["payment_id"], order_id),
        ).fetchone()
        if o["user_id"]:
            link = f"/item/{o['item_id']}" if o["item_id"] else "/more/billing"
            c.execute(
                "insert into app.notifications (user_id, title, body, link) values (%s,%s,%s,%s)",
                (o["user_id"], "결제를 마쳤어요", f"{o['order_name']} · {int(o['amount_krw']):,}원 · {until:%m/%d}까지", link),
            )  # fmt: skip
    return dict(o)


def _charge_points(c: Any, o: dict[str, Any], toss: dict[str, Any]) -> dict[str, Any]:
    """포인트 충전 승인 → 포인트 한 줄(이용권 표 payments 에는 넣지 않음 — 0083). _grant 의 같은 묶음 안에서."""
    amount = int(o["amount_krw"])
    c.execute(
        """insert into app.point_ledger (user_id, delta, reason, expires_at)
           values (%s,%s,'charge', now() + make_interval(days => %s))""",
        (o["user_id"], amount, CHARGE_EXPIRE_DAYS),
    )
    o = c.execute(
        """update app.pay_orders set status = 'paid', payment_key = %s, done_at = now()
           where order_id = %s returning """
        + _O,
        (toss.get("paymentKey"), o["order_id"]),
    ).fetchone()
    if o["user_id"]:
        c.execute(
            "insert into app.notifications (user_id, title, body, link) values (%s,%s,%s,%s)",
            (o["user_id"], "포인트를 충전했어요", f"{amount:,}P · {amount:,}원", "/points"),
        )
    return dict(o)


def _mark(order_id: str, status: str, **cols: Any) -> dict[str, Any]:
    sets = ", ".join(f"{k} = %({k})s" for k in cols)
    with connect() as c:
        o = c.execute(
            f"update app.pay_orders set status = %(status)s{', ' + sets if sets else ''} "
            "where order_id = %(oid)s and payment_id is null and status <> 'paid' returning " + _O,
            {"status": status, "oid": order_id, **cols},
        ).fetchone()
        if not o:
            o = c.execute(
                "select " + _O + " from app.pay_orders where order_id = %s", (order_id,)
            ).fetchone()
    return dict(o)


def _apply(order_id: str, toss: dict[str, Any]) -> dict[str, Any]:
    """토스 결제 상태를 주문에 반영."""
    st = toss.get("status")
    if st == "DONE":
        return _grant(order_id, toss)
    if st == "WAITING_FOR_DEPOSIT":
        va = toss.get("virtualAccount") or {}
        vb = {"bank": va.get("bankCode"), "account": va.get("accountNumber"), "due": va.get("dueDate"),
              "name": va.get("customerName")}  # fmt: skip
        from psycopg.types.json import Jsonb

        return _mark(order_id, "waiting", payment_key=toss.get("paymentKey"),
                     deposit_secret=toss.get("secret"), vbank=Jsonb(vb))  # fmt: skip
    if st in ("CANCELED", "PARTIAL_CANCELED", "EXPIRED", "ABORTED"):
        return _mark(order_id, "expired" if st == "EXPIRED" else "cancelled")
    return _mark(order_id, "ready")


def confirm(uid: str, payment_key: str, order_id: str, amount: int) -> dict[str, Any]:
    """결제창에서 돌아온 뒤: 금액을 주문과 맞춰 보고 승인 → 이용권."""
    _need_open()
    with connect() as c:
        o = c.execute(
            "select " + _O + " from app.pay_orders where order_id = %s", (order_id,)
        ).fetchone()
    if not o or str(o["user_id"]) != uid:
        raise HTTPException(404, "주문을 찾지 못했어요")
    if o["payment_id"] or o["status"] not in ("ready", "failed"):  # 충전은 payment_id 없이 paid
        return _result(dict(o))  # 새로 고침 · 두 번 누름
    if int(amount) != int(o["amount_krw"]):
        _mark(order_id, "failed", fail_code="AMOUNT", fail_msg="결제 금액이 주문과 달라요")
        raise HTTPException(400, "결제 금액이 주문과 달라 승인하지 않았어요")
    try:
        toss = _toss("POST", "/v1/payments/confirm",
                     {"paymentKey": payment_key, "orderId": order_id, "amount": int(amount)}, idem=order_id)  # fmt: skip
    except HTTPException as e:
        if "ALREADY_PROCESSED_PAYMENT" in str(e.detail):
            toss = payment(payment_key)
        else:
            _mark(order_id, "failed", fail_code="CONFIRM", fail_msg=str(e.detail)[:200])
            raise
    return _result(_apply(order_id, toss))


def order_status(uid: str, order_id: str) -> dict[str, Any]:
    with connect() as c:
        o = c.execute(
            "select " + _O + " from app.pay_orders where order_id = %s", (order_id,)
        ).fetchone()
    if not o or str(o["user_id"]) != uid:
        raise HTTPException(404, "주문을 찾지 못했어요")
    return _result(dict(o))


def fail(uid: str, order_id: str, code: str, message: str) -> None:
    """결제창에서 그만두거나 실패해 돌아옴 — 주문에 적어 둠(이용권은 그대로)."""
    with connect() as c:
        c.execute(
            """update app.pay_orders set status = 'failed', fail_code = %s, fail_msg = %s
               where order_id = %s and user_id = %s and status = 'ready'""",
            (code[:60], message[:200], order_id, uid),
        )


def webhook(body: dict[str, Any]) -> dict[str, Any]:
    """토스 웹훅. 본문은 믿지 않고 결제를 다시 조회해 반영. 입금 전용 계좌는 secret 을 주문 값과 맞춤."""
    if not is_open():
        return {"ok": False}
    event = body.get("eventType")
    if event == "PAYMENT_STATUS_CHANGED":
        key = (body.get("data") or {}).get("paymentKey")
        if not key:
            return {"ok": False}
        toss = payment(str(key))
        oid = str(toss.get("orderId") or "")
        with connect() as c:
            if not c.execute("select 1 from app.pay_orders where order_id = %s", (oid,)).fetchone():
                return {"ok": False}
        _apply(oid, toss)
        return {"ok": True}
    if event == "BILLING_DELETED":
        bk = (body.get("data") or {}).get("billingKey")
        with connect() as c:
            c.execute("update app.billing_cards set billing_key = null, updated_at = now() where billing_key = %s", (bk,))  # fmt: skip
        return {"ok": True}
    if event is None and body.get("secret") and body.get("orderId"):  # DEPOSIT_CALLBACK
        oid = str(body["orderId"])
        with connect() as c:
            o = c.execute("select payment_key, deposit_secret from app.pay_orders where order_id = %s", (oid,)).fetchone()  # fmt: skip
        if not o or not o["deposit_secret"] or not secrets.compare_digest(str(o["deposit_secret"]), str(body["secret"])):  # fmt: skip
            return {"ok": False}
        _apply(oid, payment(str(o["payment_key"])))
        return {"ok": True}
    return {"ok": True}


# ---------- 매달 자동결제 ----------


def card_start(uid: str) -> dict[str, Any]:
    """카드 등록 창을 열 값(customerKey). 등록이 끝나면 card_issue."""
    _need_open()
    return {"client_key": settings.TOSS_CLIENT_KEY, "customer_key": _customer_key(uid)}


def _charge(uid: str, billing_key: str, customer_key: str, plan: str, renew_of: int | None) -> tuple[str, dict[str, Any]]:  # fmt: skip
    """빌링키로 한 달 결제(토스 자동결제 승인 — 최대 60초)."""
    today = date.today()
    oid = new_order_id(today)
    name = order_name(plan, "month")
    amount = _amount(plan, "month")
    with connect() as c:
        c.execute(
            """insert into app.pay_orders (order_id, user_id, plan, period, amount_krw, order_name, method, renew_of)
               values (%s,%s,%s,'month',%s,%s,'billing',%s)""",
            (oid, uid, plan, amount, name, renew_of),
        )
    try:
        toss = _toss("POST", f"/v1/billing/{billing_key}",
                     {"customerKey": customer_key, "amount": amount, "orderId": oid, "orderName": name}, idem=oid)  # fmt: skip
    except HTTPException as e:
        _mark(oid, "failed", fail_code="BILLING", fail_msg=str(e.detail)[:200])
        raise
    return oid, toss


def card_issue(uid: str, auth_key: str, customer_key: str) -> dict[str, Any]:
    """카드 등록 창에서 돌아온 뒤: 빌링키 발급 → 첫 달 바로 결제 → 이용권(매달 자동)."""
    _need_open()
    with connect() as c:
        row = c.execute("select customer_key, billing_key from app.billing_cards where user_id = %s", (uid,)).fetchone()  # fmt: skip
    if not row or row["customer_key"] != customer_key:
        raise HTTPException(403, "카드 등록 정보가 맞지 않아요")
    r = _toss(
        "POST",
        "/v1/billing/authorizations/issue",
        {"authKey": auth_key, "customerKey": customer_key},
    )
    bk = str(r.get("billingKey") or "")
    if not bk:
        raise HTTPException(402, "카드를 등록하지 못했어요")
    num = str(r.get("cardNumber") or (r.get("card") or {}).get("number") or "")
    label = " ".join(x for x in (str(r.get("cardCompany") or "카드"), num[-4:]) if x).strip()
    with connect() as c:
        c.execute(
            "update app.billing_cards set billing_key = %s, card_label = %s, updated_at = now() where user_id = %s",
            (bk, label, uid),
        )
        live = c.execute(
            """select 1 from app.payments where user_id = %s and plan = 'personal' and period = 'month'
               and status in ('paid','part_refunded') and valid_to >= current_date""",
            (uid,),
        ).fetchone()
    if live:  # 이미 매달 이용권이 있으면 카드만 바꿈(다음 결제부터 이 카드)
        with connect() as c:
            c.execute(
                """update app.payments set auto_renew = true, renew_fails = 0 where user_id = %s and period = 'month'
                   and status = 'paid' and valid_to >= current_date""",
                (uid,),
            )
        return {"status": "card", "card": label}
    oid, toss = _charge(uid, bk, customer_key, "personal", None)
    if toss.get("status") != "DONE":
        _mark(
            oid,
            "failed",
            fail_code=str(toss.get("status")),
            fail_msg="첫 달 결제가 끝나지 않았어요",
        )
        raise HTTPException(402, "첫 달 결제가 끝나지 않았어요 · 카드사에 확인해 주세요")
    o = _grant(oid, toss, auto_renew=True)
    return {**_result(o), "card": label}


def renew_due() -> dict[str, Any]:
    """매일 새벽(cron): 오늘 끝나는(또는 2일 안에 끝나 아직 못 낸) 매달 이용권을 다음 달로 결제."""
    if not is_open():
        return {"open": False}
    done = failed = stopped = 0
    with connect() as c:
        due = c.execute(
            """select p.payment_id, p.user_id, p.plan, p.valid_to, p.renew_fails, b.billing_key, b.customer_key
               from app.payments p left join app.billing_cards b on b.user_id = p.user_id
               where p.period = 'month' and p.auto_renew and p.status = 'paid'
                 and p.valid_to between current_date - 2 and current_date
                 and not exists (select 1 from app.pay_orders o where o.renew_of = p.payment_id and o.status = 'paid')
               order by p.valid_to limit 200"""
        ).fetchall()
    # 한 사람씩: 카드마다 토스에 따로 결제를 보내야 하고, 한 사람 실패가 다음 사람을 막지 않게(반복 안 쿼리 — 일부러)
    for p in due:
        try:
            if not p["billing_key"]:
                raise HTTPException(402, "등록된 카드가 없어요")
            oid, toss = _charge(
                str(p["user_id"]), p["billing_key"], p["customer_key"], p["plan"], p["payment_id"]
            )
            if toss.get("status") != "DONE":
                raise HTTPException(402, f"결제 상태 {toss.get('status')}")
            start = max(p["valid_to"] + timedelta(days=1), date.today())
            _grant(oid, toss, auto_renew=True, start=start)
            with connect() as c:
                c.execute(
                    "update app.payments set auto_renew = false where payment_id = %s",
                    (p["payment_id"],),
                )
            done += 1
        except Exception as e:  # noqa: BLE001 — 한 사람 실패가 다음 사람을 막지 않게
            failed += 1
            if not isinstance(e, HTTPException):
                from aucs_api.services import errors as error_log

                error_log.save(
                    "api",
                    f"매달 결제 {p['payment_id']}: {type(e).__name__}: {e}",
                    path="cron/renew",
                )
            n = int(p["renew_fails"] or 0) + 1
            stop = n >= RENEW_TRIES or p["valid_to"] < date.today() - timedelta(days=1)
            stopped += int(stop)
            with connect() as c:
                c.execute(
                    "update app.payments set renew_fails = %s, auto_renew = %s where payment_id = %s",
                    (n, not stop, p["payment_id"]),
                )
                title = "매달 결제를 멈췄어요" if stop else "매달 결제가 되지 않았어요"
                why = str(e.detail) if isinstance(e, HTTPException) else "잠시 문제가 생겼어요"
                body = f"{why[:80]} · " + (
                    "카드를 다시 등록해 주세요" if stop else "내일 다시 해 볼게요"
                )
                c.execute(
                    "insert into app.notifications (user_id, title, body, link) values (%s,%s,%s,'/more/billing')",
                    (p["user_id"], title, body[:120]),
                )
    return {"open": True, "due": len(due), "done": done, "failed": failed, "stopped": stopped}
