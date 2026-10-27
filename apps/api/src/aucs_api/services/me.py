"""회원 자료 (관심·조건·푸시·알림함·프로필). API는 DB 관리자 연결이라 모든 쿼리에 user_id 를 겁니다."""

from typing import Any

from psycopg.types.json import Jsonb

from aucs_api.db import batch, connect
from aucs_api.services.items import card

_WATCH_SQL = """
select i.item_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.sido, i.sigungu, i.gu, i.address,
       i.building_desc, i.building_area_m2, i.appraisal_krw, i.min_price_krw, i.failed_count, i.is_share,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals, '{}'::json as data_status, w.step, w.in_compare,
       (select max(e.created_at) from app.alert_events e
         where e.user_id = w.user_id and e.item_id = i.item_id and e.prev_value is not null) as changed_at
from app.watch_items w
join core.items i on i.item_id = w.item_id
join core.cases c using (case_id)
left join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id order by version desc limit 1) a on true
where w.user_id = %s
order by i.sale_date nulls last
"""


# 관심 단계(WATCH-01, 10/19 7단계): 발견 → 서류 → 현장 → 자금 → 입찰 준비 → 결과 → 잔금·명도.
# 결과는 매각기일이 지나면 저절로, 낙찰 뒤 「잔금·명도」는 회원이 옮김.
STEPS = ("found", "review", "field", "money", "bid", "after")


def watch_step(step: str | None, sale_date: Any, today: Any) -> str:
    if step == "after":
        return "after"
    if sale_date and sale_date < today:
        return "result"
    return step if step in STEPS else "found"


def watch_list(uid: str, today: Any) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(_WATCH_SQL, (uid,)).fetchall()
    return [watch_card(r, today) for r in rows]


CHANGED_DAYS = 3  # 관심 목록 「바뀜」 표시: 최근 이만큼 안에 기일·최저가·결과가 바뀐 물건(WATCH-01)


def watch_card(r: dict[str, Any], today: Any) -> dict[str, Any]:
    ch = r.get("changed_at")
    return {
        **card(r, today),
        "step": watch_step(r["step"], r["sale_date"], today),
        "in_compare": r["in_compare"],
        "changed": bool(ch and (today - ch.date()).days <= CHANGED_DAYS),
    }


def watch_set_step(uid: str, item_id: str, step: str) -> bool:
    if step not in STEPS:
        return False
    with connect() as c:
        n = c.execute(
            "update app.watch_items set step = %s where user_id = %s and item_id = %s",
            (step, uid, item_id),
        ).rowcount
    return n > 0


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
            """select n.noti_id, n.title, n.body, n.link, n.read_at, n.created_at, e.kind
               from app.notifications n left join app.alert_events e on e.event_id = n.event_id
               where n.user_id = %s order by n.created_at desc limit 100""",
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
        q_rows, q_hol, q_todo = batch(
            c,
            [
                (_BIDS_SQL, (uid,)),
                ("select holiday_date from ref.holidays where checked", None),
                (
                    """select i.item_id, i.sale_date,
                      coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '') as place
               from app.watch_items w join core.items i using (item_id)
               where w.user_id = %s and i.sale_date <= %s and i.sale_date >= %s - 60
                 and not exists (select 1 from app.bid_results b where b.user_id = w.user_id
                                 and b.item_id = i.item_id and b.sale_date = i.sale_date)
               order by i.sale_date desc""",
                    (uid, today, today),
                ),
            ],
        )
        rows = q_rows.fetchall()
        hol = [r["holiday_date"] for r in q_hol.fetchall()]
        todo = q_todo.fetchall()
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


# 물건 작업 공간(WATCH-02): 메모·내 확인 체크·저장한 입찰가·변경 이력
MAX_CALCS = 5
_KIND_KO = {
    "sale_date": "매각기일",
    "min_price": "최저가",
    "result": "결과",
    "listing": "법원 목록",
}
_VALUE_KO = {"gone": "빠짐", "listed": "목록에 있음", "sold": "매각", "failed": "유찰",
             "changed": "변경", "withdrawn": "취하", "dismissed": "기각"}  # fmt: skip


def _val(kind: str, v: str | None) -> str:
    if v is None:
        return "-"
    if kind == "min_price" and v.isdigit():
        n = int(v) // 10_000
        eok, man = divmod(n, 10_000)
        return f"{eok}억 {man:,}만" if eok and man else (f"{eok}억" if eok else f"{man:,}만")
    return _VALUE_KO.get(v, v)


def history_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """알림 기록 → 변경 이력 줄 (처음 기준값은 빼고 실제로 바뀐 것만)."""
    return [
        {
            "at": r["created_at"].strftime("%Y-%m-%d"),
            "what": _KIND_KO.get(r["kind"], r["kind"]),
            "change": f"{_val(r['kind'], r['prev_value'])} → {_val(r['kind'], r['new_value'])}",
        }
        for r in rows
        if r["prev_value"] is not None and r["kind"] in _KIND_KO
    ]


def workspace(uid: str, item_id: str, today: Any) -> dict[str, Any] | None:
    with connect() as c:
        w = c.execute(
            """select w.step, w.memo, w.checks, w.calcs, i.sale_date from app.watch_items w
               join core.items i using (item_id) where w.user_id = %s and w.item_id = %s""",
            (uid, item_id),
        ).fetchone()
        if not w:
            return None
        ev = c.execute(
            """select kind, prev_value, new_value, created_at from app.alert_events
               where user_id = %s and item_id = %s order by created_at desc limit 30""",
            (uid, item_id),
        ).fetchall()
    return {
        "step": watch_step(w["step"], w["sale_date"], today),
        "memo": w["memo"] or "",
        "checks": w["checks"] or {},
        "calcs": w["calcs"] or [],
        "history": history_rows(ev),
    }


def _update(uid: str, item_id: str, sql: str, args: tuple[Any, ...]) -> bool:
    with connect() as c:
        n = c.execute(
            f"update app.watch_items set {sql}, updated_at = now() where user_id = %s and item_id = %s",
            (*args, uid, item_id),
        ).rowcount
    return n > 0


def ws_memo(uid: str, item_id: str, memo: str) -> bool:
    return _update(uid, item_id, "memo = %s", (memo[:2000],))


def ws_check(uid: str, item_id: str, key: str, done: bool, today: Any) -> bool:
    if done:
        return _update(uid, item_id, "checks = checks || %s", (Jsonb({key: str(today)}),))
    return _update(uid, item_id, "checks = checks - %s", (key,))


def ws_calc_add(uid: str, item_id: str, bid_krw: int, cash_krw: int | None, today: Any) -> bool:
    entry = Jsonb([{"bid_krw": bid_krw, "cash_krw": cash_krw, "saved_at": str(today)}])
    # 새 것을 앞에, 같은 금액은 하나만, 최대 5개
    return _update(
        uid,
        item_id,
        """calcs = (select coalesce(jsonb_agg(x), '[]'::jsonb) from (
                 select x from jsonb_array_elements(%s::jsonb || coalesce((
                   select jsonb_agg(y) from jsonb_array_elements(calcs) y
                   where (y->>'bid_krw')::bigint <> %s), '[]'::jsonb)) x limit %s) t)""",
        (entry, bid_krw, MAX_CALCS),
    )


def ws_calc_remove(uid: str, item_id: str, bid_krw: int) -> bool:
    return _update(
        uid,
        item_id,
        """calcs = coalesce((select jsonb_agg(y) from jsonb_array_elements(calcs) y
                   where (y->>'bid_krw')::bigint <> %s), '[]'::jsonb)""",
        (bid_krw,),
    )


# 비교함: 관심 물건 중 3~5개를 같은 기준으로. 뺄 때 이유를 남겨 다음 추천에서 덜 보여 줌
COMPARE_MAX = 5
EXCLUDE_REASONS = ("budget", "assumed_unclear", "field_bad", "other")


def compare_get(uid: str) -> dict[str, Any]:
    with connect() as c:
        q_ids, q_ex = batch(
            c,
            [
                (
                    """select w.item_id from app.watch_items w join core.items i using (item_id)
                   where w.user_id = %s and w.in_compare order by i.sale_date nulls last""",
                    (uid,),
                ),
                (
                    """select e.item_id, e.reason, e.created_at::date::text as at, c2.case_no,
                      coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '') as place
               from app.compare_exclusions e
               left join core.items i using (item_id) left join core.cases c2 on c2.case_id = i.case_id
               where e.user_id = %s order by e.created_at desc limit 50""",
                    (uid,),
                ),
            ],
        )
        ids = [r["item_id"] for r in q_ids.fetchall()]
        excluded = q_ex.fetchall()
    return {"items": ids, "excluded": excluded, "max": COMPARE_MAX}


def compare_set(uid: str, item_id: str, on: bool) -> str | None:
    """None이면 성공, 아니면 안 된 이유."""
    with connect() as c:
        if on:
            n = c.execute(
                "select count(*) as n from app.watch_items where user_id = %s and in_compare",
                (uid,),
            ).fetchone()
            if n and n["n"] >= COMPARE_MAX:
                return "full"
            c.execute(
                "delete from app.compare_exclusions where user_id = %s and item_id = %s",
                (uid, item_id),
            )
        done = c.execute(
            "update app.watch_items set in_compare = %s where user_id = %s and item_id = %s",
            (on, uid, item_id),
        ).rowcount
    return None if done else "not_watched"


def compare_exclude(uid: str, item_id: str, reason: str) -> bool:
    if reason not in EXCLUDE_REASONS:
        return False
    with connect() as c:
        c.execute(
            "update app.watch_items set in_compare = false where user_id = %s and item_id = %s",
            (uid, item_id),
        )
        c.execute(
            """insert into app.compare_exclusions (user_id, item_id, reason) values (%s, %s, %s)
               on conflict (user_id, item_id) do update set reason = excluded.reason, created_at = now()""",
            (uid, item_id, reason),
        )
    return True


def compare_unexclude(uid: str, item_id: str) -> None:
    with connect() as c:
        c.execute(
            "delete from app.compare_exclusions where user_id = %s and item_id = %s",
            (uid, item_id),
        )


_NOTI_SQL = """select n.noti_id, n.title, n.body, n.link, n.read_at, n.created_at, e.kind
               from app.notifications n left join app.alert_events e on e.event_id = n.event_id
               where n.user_id = %s order by n.created_at desc limit 100"""


def home(uid: str, today: Any) -> dict[str, Any]:
    """홈 화면에 쓰는 내 자료를 한 번에(10/27 — 예전엔 관심·알림·비교함 3번 불렀음)."""
    with connect() as c:
        q_w, q_n, q_x = batch(
            c,
            [
                (_WATCH_SQL, (uid,)),
                (_NOTI_SQL, (uid,)),
                ("select item_id from app.compare_exclusions where user_id = %s", (uid,)),
            ],
        )
        rows, notis, ex = q_w.fetchall(), q_n.fetchall(), q_x.fetchall()
    watch = [watch_card(r, today) for r in rows]
    return {"watch": watch, "notifications": notis, "excluded": [r["item_id"] for r in ex]}


def compare_full(uid: str, homes: int, first: bool, today: Any) -> dict[str, Any]:
    """비교함 화면 전부를 한 번에: 담은 물건마다 상세·계산·작업 공간(10/27 — 예전엔 물건 수 × 3번)."""
    from concurrent.futures import ThreadPoolExecutor

    from aucs_api.services import item_calc, item_detail

    base = compare_get(uid)

    def one(item_id: str) -> dict[str, Any]:
        return {
            "id": item_id,
            "d": item_detail.detail(item_id, today),
            "calc": item_calc.calc(
                item_id, bid_krw=None, homes=homes, first_time=first, loan_krw=None
            ),
            "w": workspace(uid, item_id, today),
        }

    ids = base["items"]
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(ids)))) as ex:
        cols = list(ex.map(one, ids))
    return {**base, "cols": cols}


def report_add(uid: str, item_id: str, section: str, note: str) -> int:
    """「이 값이 틀렸어요」 제보(DOC-01). 관리자 화면 검증 대기에 쌓임."""
    with connect() as c:
        row = c.execute(
            """insert into app.value_reports (user_id, item_id, section, note)
               values (%s, %s, %s, %s) returning report_id""",
            (uid, item_id, section, note),
        ).fetchone()
    return int(row["report_id"]) if row else 0
