"""회원 자료 (관심·조건·푸시·알림함·프로필). API는 DB 관리자 연결이라 모든 쿼리에 user_id 를 겁니다."""

from typing import Any

from psycopg.types.json import Jsonb

from aucs_api.db import connect
from aucs_api.services.items import card

_WATCH_SQL = """
select i.item_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.sido, i.sigungu, i.gu, i.address,
       i.building_desc, i.building_area_m2, i.appraisal_krw, i.min_price_krw, i.failed_count, i.is_share,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals, '{}'::json as data_status, w.step
from app.watch_items w
join core.items i on i.item_id = w.item_id
join core.cases c using (case_id)
left join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id order by version desc limit 1) a on true
where w.user_id = %s
order by i.sale_date nulls last
"""


def watch_list(uid: str, today: Any) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(_WATCH_SQL, (uid,)).fetchall()
    return [{**card(r, today), "step": r["step"]} for r in rows]


def watch_ids(uid: str) -> list[str]:
    with connect() as c:
        return [
            r["item_id"]
            for r in c.execute(
                "select item_id from app.watch_items where user_id = %s", (uid,)
            ).fetchall()
        ]


def watch_add(uid: str, item_id: str) -> None:
    with connect() as c:
        c.execute(
            "insert into app.watch_items (user_id, item_id) values (%s, %s) on conflict do nothing",
            (uid, item_id),
        )


def watch_remove(uid: str, item_id: str) -> None:
    with connect() as c:
        c.execute("delete from app.watch_items where user_id = %s and item_id = %s", (uid, item_id))


def searches(uid: str) -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            "select search_id, name, filters, delivery, active, created_at from app.saved_searches where user_id = %s order by search_id",
            (uid,),
        ).fetchall()


def search_add(
    uid: str, name: str, filters: dict[str, Any], delivery: str
) -> dict[str, Any] | None:
    with connect() as c:
        return c.execute(
            "insert into app.saved_searches (user_id, name, filters, delivery) values (%s,%s,%s,%s) returning search_id, name, filters, delivery, active",
            (uid, name, Jsonb(filters), delivery),
        ).fetchone()


def search_remove(uid: str, search_id: int) -> None:
    with connect() as c:
        c.execute(
            "delete from app.saved_searches where user_id = %s and search_id = %s", (uid, search_id)
        )


def push_add(uid: str, endpoint: str, p256dh: str, auth: str) -> None:
    with connect() as c:
        c.execute(
            "insert into app.push_subscriptions (user_id, endpoint, p256dh, auth) values (%s,%s,%s,%s)"
            " on conflict (endpoint) do update set user_id = excluded.user_id, p256dh = excluded.p256dh, auth = excluded.auth",
            (uid, endpoint, p256dh, auth),
        )


def notifications(uid: str) -> list[dict[str, Any]]:
    with connect() as c:
        return c.execute(
            "select noti_id, title, body, link, read_at, created_at from app.notifications where user_id = %s order by created_at desc limit 100",
            (uid,),
        ).fetchall()


def save_profile(uid: str, regions: list[str], cash: int | None, purpose: str | None) -> None:
    """시작 질문 답을 회원 프로필로 (로그인하면 다른 기기에서도 같게)."""
    db_purpose = "live" if purpose == "live" else ("invest" if purpose else None)
    with connect() as c:
        c.execute(
            "insert into app.profiles (user_id, interest_regions, cash_krw, purpose) values (%s,%s,%s,%s)"
            " on conflict (user_id) do update set interest_regions = excluded.interest_regions,"
            " cash_krw = excluded.cash_krw, purpose = excluded.purpose, updated_at = now()",
            (uid, regions, cash, db_purpose),
        )


_BIDS_SQL = """
select b.bid_id, b.item_id, b.sale_date, b.outcome, b.my_bid_krw, b.winning_bid_krw, b.second_bid_krw,
       b.bidder_count, b.pay_date, b.memo,
       coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '') as place,
       c.court_code, c.case_no
from app.bid_results b
left join core.items i on i.item_id = b.item_id
left join core.cases c on c.case_id = i.case_id
where b.user_id = %s
order by b.sale_date desc
"""


def bids(uid: str, today: Any) -> dict[str, Any]:
    """내 경매: 낙찰 받은 물건(일정 포함)·지난 기록·기록할 입찰(지난 관심 물건)."""
    from aucs_rules.schedule import after_sale

    with connect() as c:
        rows = c.execute(_BIDS_SQL, (uid,)).fetchall()
        hol = [
            r["holiday_date"]
            for r in c.execute("select holiday_date from ref.holidays where checked").fetchall()
        ]
        todo = c.execute(
            """select i.item_id, i.sale_date,
                      coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '') as place
               from app.watch_items w join core.items i using (item_id)
               where w.user_id = %s and i.sale_date <= %s and i.sale_date >= %s - 60
                 and not exists (select 1 from app.bid_results b where b.user_id = w.user_id
                                 and b.item_id = i.item_id and b.sale_date = i.sale_date)
               order by i.sale_date desc""",
            (uid, today, today),
        ).fetchall()
    won = []
    for r in rows:
        if r["outcome"] == "won":
            won.append(
                {**r, "schedule": after_sale(r["sale_date"], hol, pay_date=r["pay_date"]).value}
            )
    return {"won": won, "history": [r for r in rows if r["outcome"] != "won"], "todo": todo}


def bid_save(uid: str, body: dict[str, Any]) -> None:
    cols = [
        "outcome",
        "my_bid_krw",
        "winning_bid_krw",
        "second_bid_krw",
        "bidder_count",
        "pay_date",
        "memo",
    ]
    with connect() as c:
        c.execute(
            f"""insert into app.bid_results (user_id, item_id, sale_date, {", ".join(cols)})
                values (%s, %s, %s, {", ".join(["%s"] * len(cols))})
                on conflict (user_id, item_id, sale_date) do update set
                {", ".join(f"{k} = excluded.{k}" for k in cols)}, updated_at = now()""",
            (uid, body["item_id"], body["sale_date"], *[body.get(k) for k in cols]),
        )


def bid_remove(uid: str, bid_id: int) -> None:
    with connect() as c:
        c.execute("delete from app.bid_results where user_id = %s and bid_id = %s", (uid, bid_id))
