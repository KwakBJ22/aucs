"""물건 카드·지역 목록 (공개 화면용). display_policy = public 만, 이름은 가린 값만 내보냅니다."""

import re
from datetime import date, timedelta
from typing import Any

from aucs_rules.courts import COURTS
from aucs_rules.find_filter import ANALYSIS_JOIN, COURT_VISIBLE, VEHICLES, court_where
from aucs_rules.pick import usage_kind

from aucs_api import settings
from aucs_api.db import batch, connect

COURT_NAME = COURTS  # 법원 표는 규칙 courts.py 한 곳(11/8)

# 가까운 역 하나(직선 800m 안 ≈ 걸어서 15분 안, 11/12) — 목록·지도 카드의 「○○역 도보 약 8분」.
# 한 물건에 1ms 넘게 걸려 목록 SQL·건수 SQL 에 넣지 않고, 화면에 나갈 카드에만 따로 한 번에 붙임.
_STATION_SQL = """
select i.item_id, stn.station_name, stn.station_line, stn.station_m
from core.items i
join lateral (
  select st.name_ko as station_name, st.line_name as station_line,
         round(st_distance(st.geom, i.geom::geography))::int as station_m
  from ref.stations st
  where st.closed_date is null and st_dwithin(st.geom, i.geom::geography, 800)
  order by st.geom <-> i.geom::geography limit 1) stn on true
where i.item_id = any(%s) and i.geom is not null
"""

_CARD_SQL = f"""
select i.item_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.sido, i.sigungu, i.gu, i.address,
       i.building_desc, i.building_area_m2, i.appraisal_krw, i.min_price_krw, i.failed_count, i.is_share,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals,
       (a.result -> 'market' ->> 'price_krw')::numeric as market_krw,
       coalesce((select json_object_agg(d.data_kind, d.status) from analysis.item_data_status d where d.item_id = i.item_id), '{{}}') as data_status,
       (select p.path from core.item_photos p where p.case_id = i.case_id order by p.seq limit 1) as photo
from core.items i
join core.cases c using (case_id)
{ANALYSIS_JOIN}
where {COURT_VISIBLE}
"""  # 보이는 물건 조건(공개·부동산·목록에 있음·분석 끝)은 규칙 FIND-03 한 곳(11/8)

_COLS_END = "\nfrom core.items i\n"  # 고르는 칸이 끝나는 자리(안쪽 조회는 모두 다른 표)


def add_cols(sql: str, cols: str) -> str:
    """카드 SQL 의 고르는 칸 끝에 칸을 더함. 붙일 자리를 못 찾으면 바로 오류.

    11/14: 예전엔 글자 바꿔 끼우기(replace)가 자리를 못 찾아도 조용히 넘어가, 11/9 부터 「역 가까운 곳」 모음이
    비고 임대 목적 추천의 월세 수익률이 빠져 있었음."""
    if sql.count(_COLS_END) != 1:
        raise ValueError("카드 SQL 에 칸을 붙일 자리가 없음")
    return sql.replace(_COLS_END, f", {cols}{_COLS_END}")


def add_join(sql: str, join: str) -> str:
    """카드 SQL 의 분석 조인 앞에 조인을 더함(못 찾으면 바로 오류)."""
    if sql.count(ANALYSIS_JOIN) != 1:
        raise ValueError("카드 SQL 에 조인을 붙일 자리가 없음")
    return sql.replace(ANALYSIS_JOIN, join + ANALYSIS_JOIN)


def photo_url(path: str | None) -> str | None:
    """사진 저장소 경로 → 공개 주소(홈 추천·모아 보기·물건 상세가 같이 씀, 11/8)."""
    if not path or not settings.SUPABASE_URL:
        return None
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/item-photos/{path}"


def near_station(
    name: str | None, line: str | None, straight_m: int | None
) -> dict[str, Any] | None:
    """역 이름 · 직선거리 → 「○○역 도보 약 N분」 재료(WALK-01). 걸어서 15분 넘으면 None."""
    from aucs_rules.walk import NEAR_MIN, station_name, walk_estimate

    w = walk_estimate(straight_m).value if name else None
    if not name or not w or w["walk_min"] > NEAR_MIN:
        return None
    return {"name": station_name(name), "line": line, "straight_m": straight_m, **w}


def card(r: dict[str, Any], today: date) -> dict[str, Any]:
    """DB 한 줄 → 카드 한 장 (계산은 여기서 한 번만)."""
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    signals = r["signals"] or []
    unknown = [s for s in signals if s.get("status") == "모름"]
    flagged = [
        s
        for s in signals
        if s.get("level") in ("fatal", "high", "mid") and s.get("status") != "모름"
    ]
    return {
        "item_id": r["item_id"],
        "source": "court",
        "court": COURT_NAME.get(r["court_code"], r["court_code"]),
        "case_no": r["case_no"],
        "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
        "d_day": (r["sale_date"] - today).days if r["sale_date"] else None,
        "usage": r["usage_name"],
        "usage_kind": usage_kind(r["usage_name"]),  # 종류 판정은 규칙 한 곳(11/8)
        "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x),
        "building": r["building_desc"],
        "area_m2": float(r["building_area_m2"]) if r["building_area_m2"] else None,
        "appraisal_krw": app,
        "min_price_krw": mn,
        "min_rate": round(mn * 100 / app) if app and mn else None,
        "deposit_krw": mn // 10
        if mn
        else None,  # 입찰보증금(보통 최저가 10%) — 재매각·특별조건은 상세에서
        "failed_count": r["failed_count"],
        "below_appraisal_krw": app - mn if app and mn and app > mn else 0,
        # 최저가가 추정 시세보다 몇 % 낮은지(지도 「시세 대비」 색, 11/13) — 시세가 없으면 None
        "vs_market_pct": round((mk - mn) * 100 / mk) if (mk := r.get("market_krw")) and mn else None,
        "lat": r["lat"],
        "lon": r["lon"],
        "top_signal": flagged[0] if flagged else None,
        "unknown_count": len(unknown),
        "data_status": r["data_status"],
        "photo": photo_url(r.get("photo")),  # 카드 왼쪽 사진(없으면 화면이 종류 아이콘, 11/9)
        # 역(11/12): 모아보기는 SQL 에 이미 있고, 목록·지도는 attach_stations 가 나중에 붙임
        "station": near_station(r.get("station_name"), r.get("station_line"), r.get("station_m")),
    }


def attach_stations(c: Any, cards: list[dict[str, Any]]) -> None:
    """화면에 나갈 경매 카드에만 가까운 역을 한 번에 붙임."""
    ids = [
        x["item_id"] for x in cards if x.get("source", "court") == "court" and not x.get("station")
    ]
    if not ids:
        return
    got = {r["item_id"]: r for r in c.execute(_STATION_SQL, (ids,)).fetchall()}
    for x in cards:
        r = got.get(x["item_id"])
        if r:
            x["station"] = near_station(r["station_name"], r["station_line"], r["station_m"])


def parse_query(q: str | None) -> dict[str, Any] | None:
    """검색어 → 찾는 방법. 사건번호(2025타경55580·25-55580·55580) / 글자(단지·동네·주소)."""
    t = re.sub(r"\s+", "", q or "")
    if not t:
        return None
    if m := re.fullmatch(r"(\d{2}|\d{4})(?:타경|-)(\d{1,7})", t):
        year = m.group(1) if len(m.group(1)) == 4 else "20" + m.group(1)
        return {"kind": "case", "case_no": f"{year}타경{int(m.group(2))}"}
    if re.fullmatch(r"\d{3,7}", t):
        return {"kind": "case_suffix", "suffix": f"타경{int(t)}"}
    return {"kind": "text", "text": t}


def _q_where(
    pq: dict[str, Any] | None, case_col: str, text_cols: list[str], params: dict[str, Any]
) -> str:
    """검색 조건 SQL 조각 (글자는 띄어쓰기를 빼고 비교)."""
    if pq is None:
        return ""
    if pq["kind"] == "case":
        params["case_no"] = pq["case_no"]
        return f" and {case_col} = %(case_no)s"
    if pq["kind"] == "case_suffix":
        params["suffix"] = "%" + pq["suffix"]
        return f" and {case_col} like %(suffix)s"
    params["text"] = "%" + pq["text"] + "%"
    ors = " or ".join(f"replace(coalesce({c}, ''), ' ', '') ilike %(text)s" for c in text_cols)
    return f" and ({ors})"


def short_address(a: str | None) -> str:
    """「경기도 용인시 수지구 성복동 …」 → 「용인시 수지구 성복동」 (시도는 뺌)."""
    w = (a or "").replace(",", " ").split()
    return " ".join(w[1:4]) if len(w) > 1 else (a or "")


RESULT_GROUPS = {"sold": ("sold",), "withdrawn": ("withdrawn", "dismissed", "changed")}
RESULT_KO = {
    "sold": "매각",
    "failed": "유찰",
    "changed": "변경",
    "withdrawn": "취하",
    "dismissed": "기각",
}


def search_results(*, q: str | None, status: str, sigungu: list[str], limit: int) -> dict[str, Any]:
    """끝난 사건(매각·취하·변경…) 찾기. 같은 물건은 가장 최근 결과 하나."""
    pq = parse_query(q)
    params: dict[str, Any] = {"limit": limit}
    kinds = RESULT_GROUPS.get(status)
    where = f"s.display_policy = 'public' and coalesce(s.usage_name, '') !~ '{VEHICLES}'"
    if kinds:
        where += " and s.result = any(%(kinds)s)"
        params["kinds"] = list(kinds)
    if sigungu and pq is None:
        # 매각결과는 물건 표에 없는 사건이 많아 주소 글자로도 지역을 맞춤
        where += " and (i.sigungu = any(%(sigungu)s) or s.address ilike any(%(sg_like)s))"
        params["sigungu"] = sigungu
        params["sg_like"] = [f"%{x}%" for x in sigungu]
    where += _q_where(pq, "s.case_no", ["i.building_desc", "s.address"], params)
    sql = f"""
      select distinct on (s.court_code, s.case_no, s.item_no)
             s.result_id, s.item_id, s.court_code, s.case_no, s.sale_date, s.result, s.usage_name,
             s.appraisal_krw, s.winning_bid_krw, s.sale_rate, i.sigungu, i.gu, i.building_desc,
             s.address, i.item_id as live_item_id
      from core.sale_results s left join core.items i on i.item_id = s.item_id
      where {where}
      order by s.court_code, s.case_no, s.item_no, s.sale_date desc"""
    with connect() as c:
        rows = c.execute(
            f"select * from ({sql}) x order by sale_date desc limit %(limit)s", params
        ).fetchall()
    return {"results": [
        {
            "result_id": r["result_id"], "item_id": r["live_item_id"],
            "court": COURT_NAME.get(r["court_code"], r["court_code"]), "case_no": r["case_no"],
            "sale_date": r["sale_date"].isoformat(), "result": RESULT_KO.get(r["result"], r["result"]),
            "usage": r["usage_name"],
            "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x) or short_address(r["address"]),
            "building": r["building_desc"], "appraisal_krw": r["appraisal_krw"],
            "winning_bid_krw": r["winning_bid_krw"],
            "sale_rate": round(float(r["sale_rate"])) if r["sale_rate"] is not None else None,
        }
        for r in rows
    ]}  # fmt: skip


def list_items(
    *,
    sigungu: list[str],
    max_cash: int | None,
    sort: str,
    limit: int,
    today: date,
    q: str | None = None,
    extra: dict[str, Any] | None = None,
    source: str = "all",
) -> dict[str, Any]:
    """진행 중 물건. source: all(경매·공매 함께, 기본) · court · onbid (10/28 공매)."""
    from aucs_api.services import onbid

    queries: list[tuple[str, dict[str, Any]]] = []
    if source in ("all", "court"):
        queries += _court_query(sigungu, max_cash, sort, limit, today, q, extra)
    oq = (
        onbid.build_query(sigungu=sigungu, max_cash=max_cash, q=q, extra=extra, today=today)
        if source in ("all", "onbid")
        else None
    )
    if oq:
        osql, op = oq
        op["limit"] = limit
        queries += [
            (
                osql
                + f" order by {onbid.ORDER.get(sort, onbid.ORDER['deadline'])} limit %(limit)s",
                op,
            ),
            ("select count(*) as n from (" + osql + ") q", op),
        ]
    if not queries:
        return {"total": 0, "items": [], "exact_item_id": None}
    with connect() as c:
        res = batch(c, queries)
    court_items: list[dict[str, Any]] = []
    onbid_items: list[dict[str, Any]] = []
    total = 0
    i = 0
    if source in ("all", "court"):
        court_items = [card(r, today) for r in res[0].fetchall()]
        total += (res[1].fetchone() or {"n": 0})["n"]
        i = 2
    if oq:
        onbid_items = [onbid.onbid_card(r, today) for r in res[i].fetchall()]
        total += (res[i + 1].fetchone() or {"n": 0})["n"]
    items = onbid.merge(court_items, onbid_items, sort, limit)
    with connect() as c:
        attach_stations(c, items)
    pq = parse_query(q)
    exact = None
    if (
        len(items) == 1
        and pq is not None
        and (pq["kind"] == "case" or items[0]["source"] == "onbid")
    ):
        exact = items[0]["item_id"]
    return {"total": total, "items": items, "exact_item_id": exact}


def _court_query(
    sigungu: list[str],
    max_cash: int | None,
    sort: str,
    limit: int,
    today: date,
    q: str | None,
    extra: dict[str, Any] | None,
) -> list[tuple[str, dict[str, Any]]]:
    """경매 물건 목록 SQL 과 건수 SQL. 공매 물건관리번호 검색이면 빈 목록."""
    if q and re.fullmatch(r"\d{4}-\d{4,5}-\d{3,6}", re.sub(r"\s+", "", q)):
        return []
    pq = parse_query(q)
    if pq is not None:  # 검색할 때는 시작 질문의 지역·현금 조건을 빼고 찾음
        sigungu, max_cash = [], None
    # 찾기 조건(FIND-03): 지역·현금·조건 칸 모두 전문가 표·알림과 같은 규칙 한 곳
    more, params = court_where({**(extra or {}), "sigungu": sigungu, "max_cash": max_cash}, today)
    params["limit"] = limit
    sql = _CARD_SQL + more
    if pq is not None:
        sql += _q_where(pq, "c.case_no", ["i.building_desc", "i.address"], params)
    order = {
        "deadline": "i.sale_date, i.item_id",
        "rate": "i.min_price_krw::float / nullif(i.appraisal_krw, 0), i.sale_date",
    }
    count_sql = "select count(*) as n from (" + sql + ") q"
    sql += f" order by {order.get(sort, order['deadline'])} limit %(limit)s"
    return [(sql, params), (count_sql, params)]


MAP_MAX = 800  # 한 번에 지도에 올릴 점 — 넘으면 「확대해 보세요」(화면이 점을 묶어 보여 줌)


def _near_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """두 점(위도·경도) 사이 직선거리 m — 지도 한 화면 안이라 평면 어림으로 충분."""
    import math

    dy = (a[0] - b[0]) * 111_320
    dx = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


SOLD_DAYS = 180  # 지도에 겹쳐 보는 낙찰 사례 기간
SOLD_MAX = 300


def map_items(
    *,
    bbox: tuple[float, float, float, float],
    sigungu: list[str],
    max_cash: int | None,
    extra: dict[str, Any] | None,
    today: date,
    walk: int | None = None,
    sold: bool = False,
) -> dict[str, Any]:
    """지도 분석(11/12): 보이는 범위(서·남·동·북) 안의 진행 경매 물건 — 찾기와 같은 조건(FIND-03).

    walk(11/13 역세권 보기): 역까지 걸어서 walk 분 안(어림 WALK-01) 물건만 + 역마다 물건 수.
    sold(11/13): 같은 범위의 최근 낙찰 사례(법원에서 받은 매각결과만).
    """
    from aucs_rules.walk import DETOUR, M_PER_MIN, station_name

    more, params = court_where({**(extra or {}), "sigungu": sigungu, "max_cash": max_cash}, today)
    w, s, e, n = bbox
    params.update({"w": w, "s": s, "e": e, "n": n, "limit": MAP_MAX})
    sql = (
        _CARD_SQL
        + more
        + " and i.geom is not null"
        + " and i.geom::geometry && st_makeenvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326)"
    )
    walk_m = round(walk * M_PER_MIN / DETOUR) if walk else None
    if walk_m:
        params["walk_m"] = walk_m
        sql += (
            " and exists (select 1 from ref.stations st where st.closed_date is null"
            " and st_dwithin(st.geom, i.geom::geography, %(walk_m)s))"
        )
    out: dict[str, Any] = {"max": MAP_MAX}
    with connect() as c:
        q_rows, q_n = batch(c, [
            (sql + " order by i.sale_date, i.item_id limit %(limit)s", params),
            ("select count(*) as n from (" + sql + ") q", params),
        ])  # fmt: skip
        rows, total = q_rows.fetchall(), (q_n.fetchone() or {"n": 0})["n"]
        cards = [card(r, today) for r in rows]
        attach_stations(c, cards[:60])  # 목록에 보이는 앞쪽만(점 800개 모두에 붙이면 1초 넘음)
        out.update(total=total, items=cards)
        if walk_m:
            st_rows = c.execute(
                """select st.name_ko, st.line_name, st_y(st.geom::geometry) as lat, st_x(st.geom::geometry) as lon
                   from ref.stations st
                   where st.closed_date is null
                     and st.geom::geometry && st_expand(st_makeenvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326), 0.01)""",
                params,
            ).fetchall()
            pts = [(x["lat"], x["lon"]) for x in cards if x["lat"] is not None]
            merged: dict[str, dict[str, Any]] = {}
            for r in st_rows:  # 환승역은 노선마다 한 줄 — 이름으로 하나로
                cnt = sum(1 for p in pts if _near_m(p, (r["lat"], r["lon"])) <= walk_m)
                name = station_name(r["name_ko"])
                m = merged.setdefault(name, {"name": name, "lines": [], "lat": r["lat"], "lon": r["lon"], "count": 0})  # fmt: skip
                if r["line_name"] and r["line_name"] not in m["lines"]:
                    m["lines"].append(r["line_name"])
                m["count"] = max(m["count"], cnt)
            out["stations"] = [m for m in merged.values() if m["count"]]
            out["walk_m"] = walk_m
        if sold:
            out["sold"] = [
                {
                    "result_id": r["result_id"], "lat": r["lat"], "lon": r["lon"],
                    "sale_date": r["sale_date"].isoformat(), "usage": r["usage_name"],
                    "building": r["building_desc"], "appraisal_krw": r["appraisal_krw"],
                    "winning_bid_krw": r["winning_bid_krw"],
                    "sale_rate": float(r["sale_rate"]) if r["sale_rate"] is not None else None,
                }
                for r in c.execute(
                    f"""select distinct on (s.item_id) s.result_id, s.sale_date, s.usage_name, s.appraisal_krw,
                               s.winning_bid_krw, s.sale_rate, i.building_desc,
                               st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon
                        from core.sale_results s join core.items i on i.item_id = s.item_id
                        where s.result = 'sold' and s.origin = 'court_collect' and s.display_policy = 'public'
                          and s.sale_date >= %(sold_from)s and s.winning_bid_krw is not null
                          and coalesce(s.usage_name, '') !~ '{VEHICLES}' and i.geom is not null
                          and i.geom::geometry && st_makeenvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326)
                        order by s.item_id, s.sale_date desc limit {SOLD_MAX}""",
                    {**params, "sold_from": today - timedelta(days=SOLD_DAYS)},
                ).fetchall()
            ]  # fmt: skip
    return out


def regions() -> list[dict[str, Any]]:
    """시작 질문의 지역 고르기: 서울·경기·인천 시군구와 지금 진행 중인 물건 수(인천 11/4)."""
    with connect() as c:
        return c.execute(
            """select r.sido, r.sigungu, count(i.item_id) as items
               from (select distinct sido, split_part(sigungu, ' ', 1) as sigungu from ref.regions
                     where level = 'sigungu' and sido in ('서울특별시', '경기도', '인천광역시')) r
               left join core.items i on i.sido = r.sido and i.sigungu = r.sigungu and i.sale_date >= current_date
                 and i.status_code is distinct from 'gone'
                 and exists (select 1 from analysis.item_analysis x where x.item_id = i.item_id)
               group by 1, 2
               order by array_position(array['서울특별시', '경기도', '인천광역시'], r.sido), 2"""
        ).fetchall()


def request_docs(item_id: str) -> bool:
    """손님이 연 물건에 현황조사·문건이 없으면 그 사건 서류 받기를 줄 세움(11/4) — PC 수집기가 5분마다 받아 감.

    같은 물건은 하루에 한 번만, 이미 받았으면 줄 세우지 않음. 줄 세웠으면 True.
    """
    key = f"case_docs:{item_id}"
    with connect() as c:
        row = c.execute(
            """insert into ops.job_requests (job_key)
               select %(key)s
               where exists (select 1 from core.items where item_id = %(id)s and sale_date >= current_date)
                 and not exists (select 1 from analysis.item_data_status d where d.item_id = %(id)s
                                 and d.data_kind = 'status_report' and d.status in ('extracted', 'verified'))
                 and not exists (select 1 from ops.job_requests r where r.job_key = %(key)s
                                 and (r.status in ('waiting', 'running') or r.requested_at > now() - interval '1 day'))
               returning req_id""",
            {"key": key, "id": item_id},
        ).fetchone()
    return row is not None
