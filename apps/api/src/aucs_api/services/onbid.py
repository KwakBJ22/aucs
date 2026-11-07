"""공매(온비드) 카드·목록. 경매 카드와 같은 모양으로 내보내고 source·재산 종류·입찰 마감·다음 회차를 더함.
경매와 섞어 보여 주되 숫자(낙찰가율 분모)는 섞지 않음 — 설계: 「옥스 공매 화면설계서」 3절."""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from aucs_rules.find_filter import ONBID_VISIBLE, court_where, onbid_where
from aucs_rules.pick import usage_kind

KST = timezone(timedelta(hours=9))
KIND_KO = {
    "seized": "압류",
    "public": "국유·수탁",
    "general": "기타일반",
    "trust": "신탁",
    "finance": "금융기관",
}

_CARD_SQL = f"""
select o.*,
       (select json_build_object('min_price_krw', n.min_price_krw, 'bid_start', n.bid_start, 'bid_end', n.bid_end)
          from core.onbid_rounds n
         where n.item_id = o.item_id and n.bid_end > coalesce(o.bid_end, now()) and n.min_price_krw is not null
         order by n.bid_end limit 1) as next_round
from core.onbid_items o
where {ONBID_VISIBLE}
"""  # 보이는 공매 물건 조건은 규칙 FIND-03 한 곳(11/8)

TRUST_SIGNAL = {
    "rule_id": "onbid.trust",
    "level": "mid",
    "status": "확인 필요",
    "title": "신탁공매 · 전문가 확인 필요",
}


def _d(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    return v  # type: ignore[no-any-return]


def onbid_card(r: dict[str, Any], today: date) -> dict[str, Any]:
    """onbid_items 한 줄 → 카드 한 장(경매 card() 와 같은 칸 + 공매 칸)."""
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    end = _d(r["bid_end"])
    end_day = end.astimezone(KST).date() if end else None
    nxt = r.get("next_round")
    area = r["building_m2"] or r["land_m2"]
    return {
        "item_id": r["item_id"],
        "source": "onbid",
        "kind": r["kind"],
        "kind_name": KIND_KO.get(r["kind"], r["kind_name"]),
        "court": "",
        "case_no": r["mng_no"],
        "sale_date": end_day.isoformat() if end_day else None,
        "d_day": (end_day - today).days if end_day else None,
        "bid_end": end.isoformat() if end else None,
        "usage": r["usage_name"],
        "usage_kind": usage_kind(r["usage_name"]),  # 종류 판정은 규칙 한 곳(11/8)
        "place": " ".join(x for x in [r["sigungu"], r["dong"]] if x),
        "building": None,
        "area_m2": float(area) if area else None,
        "appraisal_krw": app,
        "min_price_krw": mn,
        "min_rate": round(mn * 100 / app) if app and mn else None,
        "deposit_krw": mn // 10 if mn else None,  # 보통 최저가 10% — 공고에 따로 있으면 상세에서
        "failed_count": r["failed_count"],
        "below_appraisal_krw": app - mn if app and mn and app > mn else 0,
        "lat": None,
        "lon": None,
        "top_signal": TRUST_SIGNAL if r["kind"] == "trust" else None,
        "unknown_count": 0,
        "data_status": {},
        "next_round": (
            {"min_price_krw": nxt["min_price_krw"], "bid_end": nxt["bid_end"]} if nxt else None
        ),
    }


_MNG = re.compile(r"\d{4}-\d{4,5}-\d{3,6}")


def _q_where(q: str | None, params: dict[str, Any]) -> str | None:
    """검색어 → SQL 조각. 사건번호(타경)면 공매엔 없음 → None."""
    t = re.sub(r"\s+", "", q or "")
    if not t:
        return ""
    if "타경" in t:
        return None
    if _MNG.fullmatch(t):
        params["mng"] = t
        return " and o.mng_no = %(mng)s"
    if re.fullmatch(r"\d{4,7}", t):  # 물건관리번호 끝자리
        params["mng_tail"] = "%-%" + t
        return " and o.mng_no like %(mng_tail)s"
    params["otext"] = "%" + t + "%"
    return (
        " and (replace(coalesce(o.title, ''), ' ', '') ilike %(otext)s"
        " or replace(coalesce(o.address, ''), ' ', '') ilike %(otext)s)"
    )


def build_query(
    *,
    sigungu: list[str],
    max_cash: int | None,
    q: str | None,
    extra: dict[str, Any] | None,
    today: date,
) -> tuple[str, dict[str, Any]] | None:
    """찾기 조건 → (SQL, 값). 공매에 해당 없는 검색이면 None. (순수 함수)"""
    sql = _CARD_SQL
    p: dict[str, Any] = {}
    qw = _q_where(q, p)
    if qw is None:
        return None
    sql += qw
    if qw:  # 검색할 때는 시작 질문의 지역·현금 조건을 빼고 찾음(경매와 같음)
        sigungu, max_cash = [], None
    # 찾기 조건은 경매와 같은 규칙 FIND-03 한 곳(11/8) — 값 이름도 경매와 같음
    f = {**(extra or {}), "sigungu": sigungu, "max_cash": max_cash}
    ow = onbid_where(f)
    if ow is None:
        return None
    _, fp = court_where(f, today)
    p.update(fp)
    sql += ow
    return sql, p


ORDER = {
    "deadline": "o.bid_end nulls last, o.item_id",
    "rate": "o.min_price_krw::float / nullif(o.appraisal_krw, 0) nulls last, o.bid_end",
}


def merge(
    court: list[dict[str, Any]], onbid: list[dict[str, Any]], sort: str, limit: int
) -> list[dict[str, Any]]:
    """경매·공매 카드를 한 줄로(마감 빠른 순 또는 최저가율 낮은 순). 날짜 없는 것은 뒤로. (순수 함수)"""
    if sort == "rate":

        def key(c: dict[str, Any]) -> tuple[Any, ...]:
            return (c["min_rate"] is None, c["min_rate"] or 0, c["sale_date"] or "9999")
    else:

        def key(c: dict[str, Any]) -> tuple[Any, ...]:
            return (c["sale_date"] is None, c["sale_date"] or "", c["item_id"])

    return sorted([*court, *onbid], key=key)[:limit]
