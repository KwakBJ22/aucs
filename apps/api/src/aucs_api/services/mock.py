"""모의입찰과 복기 (내 경매 > 내 분석 노트). 결과 뒤 세 가지만 돌아봄:
① 낙찰될 수 있던 가격이었나 ② 내 상한에 맞았나 ③ 안 들어간 판단도 맞았나. 적중률·순위는 없음."""

from datetime import date
from typing import Any

from aucs_rules.fmt import man_text as won

from aucs_api.db import connect


def review(m: dict[str, Any], result: str | None, winning: int | None) -> list[str]:
    """모의입찰 한 줄 → 돌아보기 문장들 (순수 함수)."""
    bid, cap, skip = m.get("bid_krw"), m.get("max_krw"), m.get("decision") == "skip"
    if result is None:
        return ["결과가 나오면 여기서 돌아볼 수 있어요"]
    if result != "sold" or not winning:
        if result == "failed":
            lines = ["유찰됐어요 — 아무도 최저가 이상을 쓰지 않았어요"]
            if not skip and bid:
                lines.append(f"내 금액 {won(bid)}이면 낙찰됐을 거예요")
            return lines
        return ["매각되지 않았어요(변경·취하 등)"]
    lines = [f"낙찰가 {won(winning)}"]
    if not skip and bid:
        gap = bid - winning
        lines.append(
            f"① 내 금액이 {won(gap)} 높아 낙찰될 수 있었어요"
            if gap > 0
            else f"① 내 금액이 {won(-gap)} 모자랐어요"
            if gap < 0
            else "① 낙찰가와 같은 금액이었어요"
        )
    if cap:
        lines.append(
            f"② 낙찰가가 내 상한({won(cap)})보다 높았어요 — 따라갔다면 상한을 넘었어요"
            if winning > cap
            else f"② 낙찰가가 내 상한({won(cap)}) 안이었어요"
        )
    if skip:
        lines.append(
            "③ 안 들어간 판단: 낙찰가가 상한보다 높아 맞는 판단이었어요"
            if cap and winning > cap
            else "③ 안 들어간 판단: 상한 안에서 팔렸어요 — 뺀 이유를 다시 볼 만해요"
            if cap
            else "③ 안 들어간 판단: 상한을 남기면 다음엔 비교해 드려요"
        )
    return lines


def save(uid: str, b: dict[str, Any]) -> None:
    with connect() as c:
        c.execute(
            """insert into app.mock_bids (user_id, item_id, sale_date, decision, bid_krw, max_krw, reason)
               select %s, i.item_id, i.sale_date, %s, %s, %s, %s from core.items i where i.item_id = %s
               on conflict (user_id, item_id, sale_date) do update set decision = excluded.decision,
                 bid_krw = excluded.bid_krw, max_krw = excluded.max_krw, reason = excluded.reason, updated_at = now()""",
            (uid, b["decision"], b.get("bid_krw"), b.get("max_krw"), b.get("reason"), b["item_id"]),
        )


def remove(uid: str, mock_id: int) -> None:
    with connect() as c:
        c.execute("delete from app.mock_bids where user_id = %s and mock_id = %s", (uid, mock_id))


def listing(uid: str, today: date) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            """select m.mock_id, m.item_id, m.sale_date, m.decision, m.bid_krw, m.max_krw, m.reason,
                      coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '') as place,
                      i.sigungu, i.usage_name,
                      r.result, r.winning_bid_krw, r.address
               from app.mock_bids m
               left join core.items i using (item_id)
               left join lateral (select result, winning_bid_krw, address from core.sale_results s
                                  where s.item_id = m.item_id and s.sale_date = m.sale_date
                                  order by fetched_at desc limit 1) r on true
               where m.user_id = %s order by m.sale_date desc limit 100""",
            (uid,),
        ).fetchall()
    out = []
    for r in rows:
        res = r["result"] if r["sale_date"] <= today else None
        sigungu, usage = r.pop("sigungu", None), r.pop("usage_name", None)
        lost = (
            res == "sold"
            and r["winning_bid_krw"]
            and r["decision"] == "bid"
            and (r["bid_krw"] or 0) < r["winning_bid_krw"]
        )
        addr = r.pop("address", None) or ""
        place = (r["place"] or "").strip() or " ".join(addr.split()[1:4])  # 지난 물건은 주소로
        out.append(
            {
                **r,
                "place": place,
                "sale_date": r["sale_date"].isoformat(),
                "review": review(r, res, r["winning_bid_krw"]),
                "similar": similar(sigungu, usage, r["max_krw"] or r["bid_krw"], today)
                if lost
                else [],
            }
        )
    return out


_GROUPS = ("아파트", "오피스텔", "다세대|연립|빌라", "단독|다가구", "상가|근린|사무|업무")


def group_of(usage: str | None) -> str | None:
    """종류 묶음(비슷한 물건 찾기용). (순수 함수)"""
    import re

    return next((g for g in _GROUPS if usage and re.search(g, usage)), None)


def similar(
    sigungu: str | None, usage: str | None, cap: int | None, today: date
) -> list[dict[str, Any]]:
    """떨어진 물건과 같은 구·같은 종류, 내 금액(상한) 안에서 시작하는 진행 물건 3개."""
    g = group_of(usage)
    if not sigungu or not g or not cap:
        return []
    with connect() as c:
        rows = c.execute(
            """select i.item_id, coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '') as place,
                      i.sale_date::text as sale_date, i.min_price_krw
               from core.items i
               where i.sigungu = %s and i.usage_name ~ %s and i.sale_date >= %s
                 and i.status_code is distinct from 'gone' and i.display_policy = 'public'
                 and i.min_price_krw between %s and %s
               order by i.sale_date, i.min_price_krw desc limit 3""",
            (sigungu, g, today, int(cap * 0.5), cap),
        ).fetchall()
    return [{**x, "place": (x["place"] or "").strip()} for x in rows]
