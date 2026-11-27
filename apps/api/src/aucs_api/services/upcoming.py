"""곧 나올 물건(예정물건, 11/27 대표님 — 탱크옥션처럼 목록만이 아니라 「언제 · 얼마쯤」을 같이).

출처는 법원 배당요구종기공고(core.upcoming_cases, 수집기 court_notices). 매각공고(물건 목록 core.cases)에 들어오면 여기서 빠짐.
- 언제쯤: 우리 자료로 센 「개시결정 → 첫 매각기일」 날 수(법원마다, 사건내역 raw case_info × 물건 첫 회차).
  한 법원 표본이 MIN_N 보다 적으면 16법원 전체 값. 가운데 절반(25~75%) 구간을 달로 보여 줌.
- 얼마쯤: 같은 단지(같은 법정동 · 지번) 최근 1년 매매를 면적별로 — 감정가가 나오기 전이라 시세 참고만(입찰가 셈에 안 씀).
  호수 면적을 모르므로 거래가 많은 면적 두 가지까지.
"""

from datetime import date, timedelta
from typing import Any

from aucs_rules.courts import COURTS, court_name

from aucs_api.cache import memo
from aucs_api.db import batch, connect

KINDS = {
    "01": "토지",
    "02": "건물",
    "03": "집합건물",
}  # 자동차 · 중기 · 선박(04 · 12 · 06 · 99)은 내지 않음
MIN_N = 15  # 법원 하나 표본이 이보다 적으면 전체 값
PAGE = 30
TRADE_DAYS = 365
OLD_DAYS = 3 * 365  # 개시결정이 이보다 오래된 사건은 내지 않음(정지 · 오래 묵은 사건)

_WHERE = """
from core.upcoming_cases u
where u.list_kind = any(%(kinds)s)
  and (u.ordered_date is null or u.ordered_date > current_date - %(old)s)
  and not exists (select 1 from core.cases c where c.court_code = u.court_code and c.case_no = u.case_no)
  and (cardinality(%(sg)s::text[]) = 0 or u.sigungu = any(%(sg)s) or split_part(u.sigungu, ' ', 1) = any(%(sg)s))
"""
LIST_SQL = (
    """select u.court_code, u.case_no, u.list_kind, u.ordered_date, u.claim_deadline, u.sido, u.sigungu, u.dong,
       u.lot_no, u.building_name, u.building_detail, u.region_code"""
    + _WHERE
    + "order by u.ordered_date desc nulls last, u.court_code, u.case_no limit %(lim)s offset %(off)s"
)
COUNT_SQL = "select count(*)::int as n" + _WHERE

# 개시결정 → 첫 매각기일(신건) 날 수 — 사건내역 원본의 개시결정일 × 물건의 첫 회차(price_round 0) 매각기일
TIMING_SQL = r"""
with ci as (
  select distinct on (case_id) case_id,
         to_date(substring(payload::text from 'csCmdcYmd": "(\d{8})"'), 'YYYYMMDD') as ord
    from raw.court_doc_raw
   where doc_kind = 'case_info' and payload::text like '%%csCmdcYmd": "2%%'
   order by case_id, fetched_at desc),
f as (select case_id, min(sale_date) as first_sale from core.items where price_round = 0 group by 1)
select c.court_code, (f.first_sale - ci.ord) as days
  from ci join f using (case_id) join core.cases c using (case_id)
 where f.first_sale > ci.ord and f.first_sale - ci.ord < 1500
"""

MARKET_SQL = """
select t.region_code, t.lot_no, round(t.area_m2)::int as area, count(*)::int as n,
       percentile_cont(0.5) within group (order by t.price_krw)::bigint as mid
  from core.trades t
  join unnest(%(rc)s::text[], %(lot)s::text[]) as k(rc, lot) on t.region_code = k.rc and t.lot_no = k.lot
 where t.deal_kind = 'sale' and t.price_krw > 0 and t.deal_date >= %(since)s
   and t.prop_type in ('apt', 'officetel', 'rowhouse')
 group by 1, 2, 3
"""


def _quantiles(days: list[int]) -> tuple[int, int] | None:
    """(순수 함수) 가운데 절반 구간(25 · 75%) — 정렬해서 자리로 셈."""
    if not days:
        return None
    s = sorted(days)
    return s[(len(s) - 1) // 4], s[(3 * (len(s) - 1)) // 4]


def timing_table(rows: list[dict[str, Any]], min_n: int = MIN_N) -> dict[str, dict[str, int]]:
    """(순수 함수) 법원마다 {lo, hi, n} — 표본이 적은 법원은 전체 값(key '*')을 씀."""
    by: dict[str, list[int]] = {}
    for r in rows:
        by.setdefault(r["court_code"], []).append(int(r["days"]))
    every = [d for v in by.values() for d in v]
    out: dict[str, dict[str, int]] = {}
    q = _quantiles(every)
    if q:
        out["*"] = {"lo": q[0], "hi": q[1], "n": len(every)}
    for court, v in by.items():
        qc = _quantiles(v)
        if qc and len(v) >= min_n:
            out[court] = {"lo": qc[0], "hi": qc[1], "n": len(v)}
    return out


def expect(
    ordered: date | None, court: str, table: dict[str, dict[str, int]], today: date
) -> dict | None:
    """(순수 함수) 첫 매각기일이 올 만한 달 — 이미 지났으면 late."""
    t = table.get(court) or table.get("*")
    if not ordered or not t:
        return None
    lo, hi = ordered + timedelta(days=t["lo"]), ordered + timedelta(days=t["hi"])
    return {
        "from": f"{max(lo, today):%Y-%m}",
        "to": f"{hi:%Y-%m}",
        "late": hi < today,
        "court_wide": court not in table,
    }


def market_by_lot(rows: list[dict[str, Any]], top: int = 2) -> dict[tuple[str, str], list[dict]]:
    """(순수 함수) 지번마다 거래 많은 면적 top 개 — {area, mid, n}, 면적 작은 것부터."""
    by: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by.setdefault((r["region_code"], r["lot_no"]), []).append(r)
    out = {}
    for k, v in by.items():
        best = sorted(v, key=lambda r: -r["n"])[:top]
        out[k] = [
            {"area": r["area"], "mid": r["mid"], "n": r["n"]}
            for r in sorted(best, key=lambda r: r["area"])
        ]
    return out


@memo(ttl=6 * 3600, size=2)
def _timing() -> dict[str, dict[str, int]]:
    with connect() as c:
        return timing_table(c.execute(TIMING_SQL).fetchall())


def upcoming(*, sigungu: list[str], page: int, today: date) -> dict[str, Any]:
    p = {
        "kinds": list(KINDS),
        "old": OLD_DAYS,
        "sg": sigungu,
        "lim": PAGE,
        "off": (page - 1) * PAGE,
    }
    with connect() as c:
        cur_rows, cur_n = batch(c, [(LIST_SQL, p), (COUNT_SQL, p)])
        rows, total = cur_rows.fetchall(), int(cur_n.fetchone()["n"])
        keys = [(r["region_code"][:8] + "00", r["lot_no"]) for r in rows
                if r["list_kind"] == "03" and r["region_code"] and r["lot_no"]]  # fmt: skip
        market = {}
        if keys:
            m = c.execute(MARKET_SQL, {"rc": [k[0] for k in keys], "lot": [k[1] for k in keys],
                                       "since": today - timedelta(days=TRADE_DAYS)}).fetchall()  # fmt: skip
            market = market_by_lot(m)
    table = _timing()
    items = []
    for r in rows:
        rc = (r["region_code"] or "")[:8] + "00"
        items.append({
            "court_code": r["court_code"],
            "court": court_name(r["court_code"]),
            "case_no": r["case_no"],
            "kind": KINDS.get(r["list_kind"] or "", ""),
            "address": " ".join(x for x in (r["sigungu"], r["dong"], r["lot_no"]) if x),
            "building": " ".join(x for x in (r["building_name"], r["building_detail"]) if x) or None,
            "ordered_date": r["ordered_date"],
            "claim_deadline": r["claim_deadline"],
            "expect": expect(r["ordered_date"], r["court_code"], table, today),
            "market": market.get((rc, r["lot_no"])) or [],
        })  # fmt: skip
    return {"total": total, "page": page, "size": PAGE, "items": items}


def watch_ids(uid: str) -> list[str]:
    with connect() as c:
        rows = c.execute(
            "select court_code || ':' || case_no as k from app.upcoming_watches where user_id = %s",
            (uid,),
        ).fetchall()
    return [r["k"] for r in rows]


def watch_set(uid: str, court: str, case_no: str, on: bool) -> None:
    if court not in COURTS:
        raise ValueError("court")
    with connect() as c:
        if on:
            c.execute(
                "insert into app.upcoming_watches (user_id, court_code, case_no) values (%s, %s, %s) "
                "on conflict do nothing",
                (uid, court, case_no),
            )
        else:
            c.execute(
                "delete from app.upcoming_watches where user_id = %s and court_code = %s and case_no = %s",
                (uid, court, case_no),
            )


# ── 경매개시 알림(11/28, 3단계) — 동네(시군구 목록) · 단지(지역 코드 + 지번). 알림은 jobs/notify.py 가 보냄.
MAX_AREAS = 10


def area_get(uid: str) -> list[str]:
    with connect() as c:
        r = c.execute(
            "select sigungu from app.upcoming_areas where user_id = %s", (uid,)
        ).fetchone()
    return list(r["sigungu"]) if r else []


def area_set(uid: str, sigungu: list[str]) -> list[str]:
    """동네 알림 켜기(시군구 목록 그대로 바꿈) · 빈 목록이면 끔. 켤 때부터 새로 들어온 사건만 알림."""
    sg = list(dict.fromkeys(s.strip() for s in sigungu if s and s.strip()))[:MAX_AREAS]
    with connect() as c:
        if not sg:
            c.execute("delete from app.upcoming_areas where user_id = %s", (uid,))
        else:
            c.execute(
                "insert into app.upcoming_areas (user_id, sigungu) values (%s, %s) "
                "on conflict (user_id) do update set sigungu = excluded.sigungu",
                (uid, sg),
            )
    return sg


def lot_label(address: str | None, lot_no: str | None) -> str:
    """(순수 함수) 「경기도 안산시 단원구 와동 709-2 시온캐슬 4층401호」 → 「안산시 단원구 와동 709-2」."""
    a = (address or "").split()
    if lot_no and lot_no in a:
        a = a[: a.index(lot_no) + 1]
    if a and a[0].endswith(("도", "특별시", "광역시", "특별자치시")):
        a = a[1:]
    return " ".join(a)[:60]


LOT_OF_ITEM = "select region_code, lot_no, address from core.items where item_id = %s"


def lot_get(uid: str, item_id: str) -> bool:
    with connect() as c:
        r = c.execute(
            "select 1 from app.lot_watches w join core.items i on i.region_code = w.region_code "
            "and i.lot_no = w.lot_no where w.user_id = %s and i.item_id = %s",
            (uid, item_id),
        ).fetchone()
    return bool(r)


def lot_set(uid: str, item_id: str, on: bool) -> None:
    """물건과 같은 단지(지역 코드 + 지번) 알림 켜기 · 끄기. 지번을 모르는 물건이면 ValueError."""
    with connect() as c:
        r = c.execute(LOT_OF_ITEM, (item_id,)).fetchone()
        if not r or not r["region_code"] or not r["lot_no"]:
            raise ValueError("lot")
        if on:
            c.execute(
                "insert into app.lot_watches (user_id, region_code, lot_no, label) values (%s, %s, %s, %s) "
                "on conflict do nothing",
                (uid, r["region_code"], r["lot_no"], lot_label(r["address"], r["lot_no"])),
            )
        else:
            c.execute(
                "delete from app.lot_watches where user_id = %s and region_code = %s and lot_no = %s",
                (uid, r["region_code"], r["lot_no"]),
            )
