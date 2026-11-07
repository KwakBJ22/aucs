"""모아 보기(11/7 대표님 — 차별화 · 손님에게 쓸모 있는 것만).

모음 판단은 규칙 COLLECT-01(packages/rules/collect.py) 하나, 「기다리면 더 싸질 물건」은 홈 추천과 같은
picks.mark_next_round(실제 유찰 비율, WAIT-01). 내 지역·현금 조건을 받으면 그 안에서만. 분석 결과(매일 아침 갱신)로 그때 셈.
"""

from datetime import date
from typing import Any

from aucs_rules.collect import KEYS, CollectInput, collect
from aucs_rules.find_filter import court_where
from aucs_rules.fmt import won
from aucs_rules.pick import diversify

from aucs_api.db import connect
from aucs_api.services.items import card, photo_url
from aucs_api.services.picks import _SQL, mark_next_round, reduction_table

# 가까운 역 하나(직선 500m 안) — 역 이름·거리
_STATION = """ left join lateral (
  select st.name_ko as station_name,
         round(st_distance(st.geom::geography, i.geom::geography))::int as station_m
  from ref.stations st
  where st.closed_date is null and i.geom is not null
    and st_dwithin(st.geom::geography, i.geom::geography, 500)
  order by st.geom::geography <-> i.geom::geography limit 1) stn on true
"""


def collections(
    *, sigungu: list[str], max_cash: int | None, key: str | None, limit: int, today: date
) -> dict[str, Any]:
    """모음마다 건수는 늘 주고, 물건은 key 가 없으면 모음마다 앞 몇 건(같은 단지 1·같은 구 2건까지),
    있으면 그 모음만 limit 건 — 화면이 건수와 목록을 한 번에 받게(11/7)."""
    sql = _SQL.replace(" as photo,", " as photo, stn.station_name, stn.station_m,").replace(
        "left join lateral (select result", _STATION + "left join lateral (select result", 1
    )
    params: dict[str, Any] = {"today": today}
    more, fp = court_where(
        {"sigungu": sigungu, "max_cash": max_cash}, today
    )  # 찾기와 같은 규칙(FIND-03)
    sql += more
    params.update(fp)
    sql += " order by i.sale_date limit 20000"  # 전체 지역도 빠짐없이(11/7 — 6000 이면 먼 날 물건이 빠졌음)
    with connect() as c:
        rows = c.execute(sql, params).fetchall()
    reduction = reduction_table(today)

    groups: dict[str, list[dict[str, Any]]] = {k: [] for k in KEYS}
    for r in rows:
        an = r["analysis"] or {}
        st = (r["station_name"], r["station_m"]) if r.get("station_name") else None
        got = collect(
            CollectInput(
                appraisal_krw=r["appraisal_krw"], min_price_krw=r["min_price_krw"],
                is_share=bool(r["is_share"]), is_special=bool(r["is_special_case"]),
                analysis=an, station=st,
            )
        ).value  # fmt: skip
        cd = card(r, today)
        mark_next_round(cd, r, reduction, today)
        if "special" not in got and cd["preview"]:
            got["next"] = {
                "reason": f"다음 회차 {won(cd['min_price_krw'])}부터 · 법원 공고 전",
                "sort": 10**13 - (cd["d_day"] or 0),  # 값이 정해진 다음 회차가 맨 앞
            }
        elif "special" not in got and cd["likely_fail"] and cd.get("next_min_krw"):
            o = cd["fail_odds"]
            got["next"] = {
                "reason": f"비슷한 물건 10건 중 {o['of10']}건 유찰 · 기다리면 {won(cd['next_min_krw'])}부터",
                "sort": o["pct"] * 1000
                - (cd["d_day"] or 0),  # 유찰 비율 높은 순 → 입찰일 가까운 순(11/8)
            }
        if not got:
            continue
        cd["photo"] = photo_url(r["photo"])
        for k, v in got.items():
            groups[k].append({**cd, "why": v["reason"], "_sort": v["sort"]})

    out: dict[str, Any] = {}
    for k in KEYS:
        rows_k = groups[k]
        if key and k != key:
            out[k] = {"total": len(rows_k), "items": []}
            continue
        rows_k = sorted(rows_k, key=lambda x: -x["_sort"])
        out[k] = {
            "total": len(rows_k),
            "items": rows_k[:limit] if key else diversify(rows_k, limit),
        }
        for x in out[k]["items"]:
            x.pop("_sort", None)
    return out
