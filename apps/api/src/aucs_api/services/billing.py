"""이용권·결제 내역과 환불(11/3 대표님 결정).

환불 규칙(이용권 화면·약관과 같은 내용):
1. 모든 이용권: 결제 7일 안에 물건 상세를 한 번도 안 열었으면 전액(전자상거래법 제17조 청약철회).
   「사용」= 결제 뒤 물건 상세를 연 것(무료로 보이는 결론·한 줄 판정은 사용 아님) — 결제 화면에 미리 알림.
2. 매달: 7일 안 해지 → 쓴 날만 뺌(한 달 요금 ÷ 30 × 쓴 날, 위약금 없음 — 소비자분쟁해결기준)
         7일 뒤 해지 → 그 달 끝까지 쓰고 다음 결제부터 멈춤(돌려줄 돈 없음).
3. 1년: 쓴 기간을 매달 요금으로 계산하고 위약금은 없음 → 「중간에 그만두면 그동안 매달권을 쓴 것과 같게」.
   (날짜로 나누면 5개월쯤부터 매달권보다 싸게 쓰고 나갈 수 있어 이 방식으로 정함)
4. 한 건: 상세를 열기 전이면 전액, 연 뒤면 없음(취하·정지·변경은 관리자가 다른 물건으로 바꿔 줌).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from aucs_api.db import connect

FREE_DAYS = 7
# 매달 요금(이용권 화면과 같게, 결제를 붙일 때 가격표 한 곳으로 옮김) — 1년권 중간 해지 계산에 씀
MONTHLY_KRW = {"personal": 29_000, "pro": 99_000}


@dataclass(frozen=True)
class Refund:
    amount_krw: int
    rule: str  # 화면에 보일 한 줄


def refund_estimate(
    period: str,
    amount: int,
    paid: date,
    today: date,
    valid_to: date,
    opened: bool,
    monthly: int = 0,
) -> Refund:
    """환불 금액 계산(순수 함수). 쓴 날은 결제일부터 오늘까지(오늘 포함). monthly = 그 이용권의 매달 요금."""
    days = (today - paid).days + 1
    if days <= FREE_DAYS and not opened:
        return Refund(amount, "7일 안 · 상세를 열지 않아 전액")
    if period == "month":
        if days <= FREE_DAYS:
            return Refund(
                max(0, amount - round(amount * days / 30)), f"7일 안 · 쓴 {days}일만 빼요"
            )
        return Refund(0, "그 달 끝까지 쓰고 다음 결제부터 멈춰요")
    if period == "one":
        return Refund(0, "이 물건 상세를 이미 열었어요")
    used = round((monthly or amount / 12) * days / 30)
    return Refund(max(0, amount - used), f"쓴 {days}일을 매달 요금으로 빼요")


def _opened(c: Any, uid: str, paid_at: Any, item_id: str | None) -> bool:
    """결제 뒤 물건 상세를 연 적이 있는지(사용 기록 app.events). 한 건 이용권은 그 물건만."""
    if item_id:
        q = "select 1 from app.events where user_id = %s and kind = 'item_view' and at >= %s and item_id = %s limit 1"
        return c.execute(q, (uid, paid_at, item_id)).fetchone() is not None
    q = "select 1 from app.events where user_id = %s and kind = 'item_view' and at >= %s limit 1"
    return c.execute(q, (uid, paid_at)).fetchone() is not None


def my_billing(uid: str) -> dict[str, Any]:
    """지금 이용권 + 결제 내역(관리자가 준 이용권 포함) + 결제마다 지금 환불하면 얼마인지."""
    today = date.today()
    with connect() as c:
        pays = c.execute(
            """select p.payment_id, p.plan, p.period, p.amount_krw, p.item_id, p.status, p.refunded_krw, p.auto_renew,
                      p.method_note, p.order_id, p.receipt_url, p.paid_at, p.valid_from, p.valid_to,
                      (select r.status from app.refund_requests r where r.payment_id = p.payment_id
                        order by r.request_id desc limit 1) as refund_status
               from app.payments p where p.user_id = %s order by p.paid_at desc limit 50""",
            (uid,),
        ).fetchall()
        for p in pays:
            if p["status"] == "paid" and p["valid_to"] >= today and p["refund_status"] != "waiting":
                r = refund_estimate(p["period"], p["amount_krw"], p["paid_at"].date(), today, p["valid_to"],
                                    _opened(c, uid, p["paid_at"], p["item_id"]), MONTHLY_KRW.get(p["plan"], 0))  # fmt: skip
                p["refund"] = {"amount_krw": r.amount_krw, "rule": r.rule}
            else:
                p["refund"] = None
        grants = c.execute(
            "select plan, until_date, reason, created_at from app.grants where user_id = %s order by created_at desc limit 20",
            (uid,),
        ).fetchall()
    now = [
        {"plan": p["plan"], "until": p["valid_to"], "auto_renew": p["auto_renew"], "period": p["period"],
         "amount_krw": p["amount_krw"], "item_id": p["item_id"]}
        for p in pays if p["status"] == "paid" and p["valid_to"] >= today
    ] + [
        {"plan": g["plan"], "until": g["until_date"], "auto_renew": False, "period": "grant", "amount_krw": 0, "item_id": None}
        for g in grants if g["until_date"] >= today
    ]  # fmt: skip
    now.sort(key=lambda x: x["until"], reverse=True)
    return {"current": now, "payments": pays, "grants": grants}


def request_refund(uid: str, payment_id: int, reason: str | None) -> dict[str, Any] | None:
    """환불 요청: 지금 규칙으로 계산한 금액을 함께 남김 → 관리자 「회원 › 환불 요청」에서 처리."""
    today = date.today()
    with connect() as c:
        p = c.execute(
            "select * from app.payments where payment_id = %s and user_id = %s and status = 'paid'",
            (payment_id, uid),
        ).fetchone()
        if not p:
            return None
        r = refund_estimate(p["period"], p["amount_krw"], p["paid_at"].date(), today, p["valid_to"],
                            _opened(c, uid, p["paid_at"], p["item_id"]), MONTHLY_KRW.get(p["plan"], 0))  # fmt: skip
        if p["period"] == "month" and r.amount_krw == 0:
            c.execute(
                "update app.payments set auto_renew = false where payment_id = %s", (payment_id,)
            )
            return {"estimate_krw": 0, "rule": r.rule, "stopped": True}
        row = c.execute(
            """insert into app.refund_requests (payment_id, user_id, estimate_krw, reason) values (%s,%s,%s,%s)
               on conflict do nothing returning request_id""",
            (payment_id, uid, r.amount_krw, reason),
        ).fetchone()
    return {
        "estimate_krw": r.amount_krw,
        "rule": r.rule,
        "request_id": row["request_id"] if row else None,
    }


def stop_renew(uid: str, payment_id: int) -> bool:
    with connect() as c:
        r = c.execute(
            "update app.payments set auto_renew = false where payment_id = %s and user_id = %s returning payment_id",
            (payment_id, uid),
        ).fetchone()
    return r is not None


def refund_requests(only_waiting: bool = True) -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            """select r.request_id, r.payment_id, r.estimate_krw, r.reason, r.status, r.answer, r.created_at,
                      p.plan, p.period, p.amount_krw, p.paid_at, p.order_id, u.email
               from app.refund_requests r join app.payments p using (payment_id)
               left join auth.users u on u.id = r.user_id
               where not %s or r.status = 'waiting' order by r.created_at limit 100""",
            (only_waiting,),
        ).fetchall()


def decide_refund(
    actor: str | None, request_id: int, ok: bool, amount: int | None, answer: str
) -> bool:
    """환불 처리(대표만). 승인하면 결제를 환불됨으로 표시하고 회원에게 알림.
    실제 카드 취소는 토스페이먼츠를 붙이면 여기서 취소 API를 부름(그 전엔 관리자가 직접)."""
    from aucs_api.services.admin_ops import audit

    with connect() as c:
        r = c.execute(
            "select * from app.refund_requests where request_id = %s and status = 'waiting'",
            (request_id,),
        ).fetchone()
        if not r:
            return False
        money = r["estimate_krw"] if amount is None else amount
        c.execute(
            "update app.refund_requests set status = %s, answer = %s, decided_by = %s, decided_at = now() where request_id = %s",
            ("done" if ok else "rejected", answer, actor, request_id),
        )
        if ok:
            c.execute(
                """update app.payments set refunded_krw = refunded_krw + %s, auto_renew = false,
                          status = case when refunded_krw + %s >= amount_krw then 'refunded' else 'part_refunded' end,
                          valid_to = least(valid_to, current_date)
                   where payment_id = %s""",
                (money, money, r["payment_id"]),
            )
        if r["user_id"]:
            title = "환불을 마쳤어요" if ok else "환불 요청을 확인했어요"
            body = f"{money:,}원 · {answer}" if ok else answer
            c.execute(
                "insert into app.notifications (user_id, title, body, link) values (%s,%s,%s,'/more/billing')",
                (r["user_id"], title, body[:120]),
            )
        audit(c, actor, "refund_done" if ok else "refund_rejected", str(request_id), {"estimate": r["estimate_krw"]},
              {"amount": money if ok else 0}, answer)  # fmt: skip
    return True
