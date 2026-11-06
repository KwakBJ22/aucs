"""홈 「오늘의 추천」·「마감 임박」·「다음 달 더 싸지는 물건」(11/4 대표님).

점수는 규칙 PICK-01(packages/rules/pick.py) 하나로 — 분석 결과(매일 아침 갱신)에서 그때 셈하므로 그날은 누구에게나 같은 값.
11/7 대표님: 사진 없는 물건은 홈 세 칸 어디에도 띄우지 않음(법원은 입찰 2주 전쯤 사진을 올림).
- 추천: 공고된 물건은 입찰 14일 안(1~14일) + 유찰 뒤 다음 회차(공고 전, 30일 안 — 지난 회차 사진이 있음) ·
  점수 순 · 같은 단지 1건·같은 구 2건까지
- 마감 임박: 7일 안 · 점수 70 이상만 짧게
- 다음 달 더 싸지는 물건: ① 유찰 뒤 다음 기일이 잡힌 물건(공고 전, status_code='preview') ② 지금 최저가가
  같은 법원 낙찰가율보다 높아 이번엔 유찰될 것 같은 물건 — 「유찰되면 ○○원부터」
"""

from datetime import date
from typing import Any

from aucs_rules.pick import PickInput, diversify, pick_score
from aucs_rules.sale_rate import next_round_min_price

from aucs_api import settings
from aucs_api.db import connect
from aucs_api.services.items import _CARD_SQL, card

PREVIEW = "preview"  # 유찰 뒤 기일내역으로 미리 안 다음 회차(법원 공고 전)

_SQL = (
    _CARD_SQL.replace(
        "a.result -> 'top' as top,",
        "a.result -> 'top' as top, jsonb_build_object('market', a.result -> 'market', 'sale_rate', a.result -> 'sale_rate',"
        " 'court_cell', a.result -> 'court_cell', 'redev', a.result -> 'redev', 'new_item', a.result -> 'new_item',"
        " 'tenant_count', a.result -> 'tenant_count', 'signals', a.result -> 'signals', 'appraisal', a.result -> 'appraisal') as analysis,"
        " i.is_special_case, i.status_code,"
        " (select p.path from core.item_photos p where p.case_id = i.case_id order by p.seq limit 1) as photo,",
    )
    # 공고 전 다음 회차는 「법원 목록에서 빠짐」과 다름 — _CARD_SQL 의 gone 걸러내기는 그대로 둠
)


def _photo_url(path: str | None) -> str | None:
    if not path or not settings.SUPABASE_URL:
        return None
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/item-photos/{path}"


def _pick_window(x: dict[str, Any]) -> bool:
    """추천 칸에 넣을 때(11/7): 공고된 물건 입찰 1~14일 남음, 유찰 뒤 다음 회차는 30일 안."""
    d = x["d_day"] if x["d_day"] is not None else -1
    return 1 <= d <= 30 if x["preview"] else 1 <= d <= 14


def home_picks(
    *, sigungu: list[str], max_cash: int | None, purpose: str | None, today: date
) -> dict[str, Any]:
    """내 지역·현금 안 물건을 PICK-01 로 매겨 세 칸으로 나눔. purpose 가 없으면(로그인 전) 목적 점수 없이 점수 큰 것 위주."""
    if purpose == "resell":  # 시작 질문 「매도(되팔기)」 = 규칙의 투자 목적
        purpose = "invest"
    sql = _SQL
    if (
        purpose == "rent"
    ):  # 임대 목적만: 같은 단지(전용 ±3㎡) 1년 월세 가운데값 — 물건 상세 「세놓으면」과 같은 자료
        sql = sql.replace(
            " as photo,",
            " as photo, rl.monthly_krw as rent_monthly, rl.deposit_krw as rent_deposit,",
        ).replace(
            "left join lateral (select result",
            """left join lateral (
  select percentile_cont(0.5) within group (order by t.monthly_rent_krw)::bigint as monthly_krw,
         percentile_cont(0.5) within group (order by t.deposit_krw)::bigint as deposit_krw
  from core.trades t
  where t.region_code = left(i.region_code, 8) || '00' and t.lot_no = i.lot_no and t.deal_kind = 'lease'
    and t.monthly_rent_krw > 0 and t.deal_date >= %(today)s::date - 366
    and (i.building_area_m2 is null or abs(t.area_m2 - i.building_area_m2) <= 3)) rl on true
left join lateral (select result""",
        )
    params: dict[str, Any] = {"today": today}
    if sigungu:
        sql += " and i.sigungu = any(%(sigungu)s)"
        params["sigungu"] = sigungu
    if max_cash:
        sql += " and i.min_price_krw / 10 <= %(max_cash)s"
        params["max_cash"] = max_cash
    sql += " order by i.sale_date limit 4000"
    with connect() as c:
        rows = c.execute(sql, params).fetchall()
        red = c.execute(
            "select value from ref.rule_tables where rule_key = 'court_reduction_pct'"
            " and valid_from <= %s order by valid_from desc limit 1",
            (today,),
        ).fetchone()
    reduction: dict[str, Any] = dict((red or {}).get("value") or {})

    scored: list[dict[str, Any]] = []
    for r in rows:
        if not r["photo"]:  # 사진 없는 물건은 홈에 안 띄움(11/7)
            continue
        an = r["analysis"] or {}
        p = pick_score(
            PickInput(
                usage=r["usage_name"], appraisal_krw=r["appraisal_krw"], min_price_krw=r["min_price_krw"],
                failed_count=r["failed_count"],
                area_m2=float(r["building_area_m2"]) if r["building_area_m2"] else None,
                is_share=bool(r["is_share"]), is_special=bool(r["is_special_case"]), analysis=an,
                d_day=(r["sale_date"] - today).days if r["sale_date"] else None,
                rent={"monthly_krw": r.get("rent_monthly"), "deposit_krw": r.get("rent_deposit")},
            ),
            purpose,
        ).value  # fmt: skip
        if p["excluded"]:
            continue
        cd = card(r, today)
        cd["score"] = p["score"]
        cd["reasons"] = p["reasons"]
        cd["photo"] = _photo_url(r["photo"])
        cd["preview"] = r["status_code"] == PREVIEW
        cc = (an.get("court_cell") or {}).get("p75")
        rate = cd["min_rate"]
        red_pct = (reduction.get(r["court_code"]) or {}).get("pct")
        cd["likely_fail"] = bool(cc and rate and rate > float(cc) + 5 and not cd["preview"])
        if cd["likely_fail"] and r["min_price_krw"]:
            cd["next_min_krw"] = next_round_min_price(r["min_price_krw"], red_pct).value
        scored.append(cd)
    scored.sort(key=lambda x: -x["score"])

    picks = diversify([x for x in scored if _pick_window(x)], 8)
    seen = {x["item_id"] for x in picks}
    soon = diversify(
        [x for x in scored if 0 <= (x["d_day"] or 0) <= 7 and x["score"] >= 70 and x["item_id"] not in seen], 4
    )  # fmt: skip
    seen |= {x["item_id"] for x in soon}
    nxt = diversify(
        [x for x in scored if (x["preview"] or x["likely_fail"]) and x["item_id"] not in seen], 6
    )
    return {"picks": picks, "soon": soon, "next": nxt}
