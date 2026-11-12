"""관리자 「이용권·포인트」 메뉴(11/12 대표님): 가격 · 이용권 현황 · 결제 · 포인트 내역 · 포인트 조정.

가격은 기준표 `plans`(새 버전 = 다음 결제부터), 포인트 값은 기준표 `points`. 화면 /plans 도 같은 기준표를 읽는다.
"""

from typing import Any

from aucs_api.db import batch, connect
from aucs_api.services.admin_ops import audit, mask
from aucs_api.services.billing import prices

_PRICE_SQL = """select valid_from, value, basis, reviewed_at from ref.rule_tables
                where rule_key = 'plans' order by valid_from desc limit 5"""


def screen() -> dict[str, Any]:
    """이용권·포인트 한 화면 자료 한 번에."""
    with connect() as c:
        q_price, q_plan, q_pay, q_month, q_pt, q_kind, q_top, q_led = batch(c, [
            (_PRICE_SQL, None),
            # 지금 쓰는 이용권: 관리자가 준 것(grants) + 결제한 것(payments)
            ("""select plan, 'grant' as src, count(distinct user_id) as n from app.grants
                where until_date >= current_date group by plan
                union all
                select plan, 'paid', count(distinct user_id) from app.payments
                where status in ('paid','part_refunded') and valid_to >= current_date group by plan""", None),
            ("""select p.payment_id, p.plan, p.period, p.amount_krw, p.refunded_krw, p.points_used, p.status,
                       p.paid_at, u.email
                from app.payments p left join auth.users u on u.id = p.user_id
                order by p.paid_at desc limit 30""", None),
            ("""select coalesce(sum(amount_krw - refunded_krw), 0) as krw, count(*) as n from app.payments
                where paid_at >= date_trunc('month', now() at time zone 'Asia/Seoul')""", None),
            ("""select coalesce(sum(delta) filter (where delta > 0), 0) as earned,
                       coalesce(-sum(delta) filter (where delta < 0), 0) as spent,
                       coalesce(sum(delta) filter (where delta > 0 and (expires_at is null or expires_at > now())), 0)
                         + coalesce(sum(delta) filter (where delta < 0), 0) as left_,
                       count(distinct user_id) filter (where delta > 0) as people
                from app.point_ledger""", None),
            # 최근 30일 올린 서류(종류 · 결과별)
            ("""select kind, status, count(*) as n, coalesce(sum(points), 0) as pts from app.contrib_uploads
                where created_at > now() - interval '30 days' group by kind, status""", None),
            ("""select l.user_id, u.email, sum(l.delta) as earned, count(*) as n from app.point_ledger l
                left join auth.users u on u.id = l.user_id
                where l.delta > 0 group by l.user_id, u.email order by earned desc limit 10""", None),
            ("""select l.entry_id, l.delta, l.reason, l.item_id, l.created_at, u.email from app.point_ledger l
                left join auth.users u on u.id = l.user_id order by l.entry_id desc limit 40""", None),
        ])  # fmt: skip
        price_rows = q_price.fetchall()
        plans: dict[str, dict[str, int]] = {}
        for r in q_plan.fetchall():
            plans.setdefault(r["plan"], {})[r["src"]] = int(r["n"])
        pays = q_pay.fetchall()
        month = q_month.fetchone()
        pt = q_pt.fetchone() or {}
        kinds = q_kind.fetchall()
        top = q_top.fetchall()
        led = q_led.fetchall()
    for rows in (pays, top, led):
        for r in rows:
            r["email"] = mask(r.get("email"))
    return {
        "prices": prices(),
        "price_rows": price_rows,
        "plans": plans,
        "payments": pays,
        "month": month,
        "points": {
            "earned": int(pt.get("earned") or 0),
            "spent": int(pt.get("spent") or 0),
            "left": max(0, int(pt.get("left_") or 0)),
            "people": int(pt.get("people") or 0),
        },
        "uploads": kinds,
        "top": top,
        "ledger": led,
    }


def user_points(uid: str) -> int:
    """한 회원의 지금 포인트(기한 안 받은 것 + 쓴 것)."""
    with connect() as c:
        r = c.execute(
            """select coalesce(sum(delta) filter (where delta > 0 and (expires_at is null or expires_at > now())), 0)
                      + coalesce(sum(delta) filter (where delta < 0), 0) as b
               from app.point_ledger where user_id = %s""",
            (uid,),
        ).fetchone()
    return max(0, int(r["b"])) if r else 0


def adjust_points(actor: str | None, uid: str, delta: int, reason: str) -> dict[str, Any] | None:
    """관리자가 포인트 더하기(+)·빼기(−). 이유는 감사 기록에, 회원 알림함에 한 줄. 빼기는 가진 만큼까지만."""
    with connect() as c:
        if not c.execute("select 1 from auth.users where id = %s", (uid,)).fetchone():
            return None
        t = c.execute(
            "select value from ref.rule_tables where rule_key = 'points' and valid_from <= current_date "
            "order by valid_from desc limit 1"
        ).fetchone()
        rule = dict(t["value"]) if t else {}
    before = user_points(uid)
    if delta < 0:
        delta = -min(-delta, before)
        if delta == 0:
            return {"balance": before, "delta": 0}
    with connect() as c:
        c.execute(
            # 받은 포인트의 기한은 서류 포인트와 같은 규칙(무료 기간이면 비움 — 전환일부터 1년)
            """insert into app.point_ledger (user_id, delta, reason, expires_at)
               values (%s, %s, 'admin', case when %s then now() + make_interval(days => %s) end)""",
            (
                uid,
                delta,
                delta > 0 and not rule.get("free_period"),
                int(rule.get("expire_days") or 365),
            ),
        )
        c.execute(
            "insert into app.notifications (user_id, title, body, link) values (%s, %s, %s, '/points')",
            (
                uid,
                "포인트를 받았어요" if delta > 0 else "포인트가 줄었어요",
                f"{abs(delta):,}P · {reason}",
            ),
        )
        audit(
            c,
            actor,
            "points",
            uid,
            {"balance": before},
            {"balance": before + delta, "delta": delta},
            reason,
        )
    return {"balance": before + delta, "delta": delta}
