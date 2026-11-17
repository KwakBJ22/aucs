"""아카데미 3단계(11/17): 오늘의 물건 문제 — 우리가 법원에서 받은 실제 물건 · 낙찰 결과로 하루 한 문제.

정답은 계산으로만 나오는 것만 냄(낙찰가율 · 최저가가 감정가의 몇 %). 우리 분석(떠안는 권리 등)을 정답으로 쓰지 않음 —
분석이 틀릴 수 있어서. 같은 날에는 누구에게나 같은 문제(한국 날짜로 고름).
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from aucs_api.db import connect

KST = timezone(timedelta(hours=9))

_SOLD_SQL = """select r.item_id, r.sido, r.usage_name, r.appraisal_krw, r.winning_bid_krw, r.sale_date
    from core.sale_results r
    where r.result = 'sold' and r.origin = 'court_collect' and r.appraisal_krw > 0 and r.winning_bid_krw > 0
      and r.sale_date >= current_date - 14 and r.is_share is not true and r.is_special_case is not true
      and coalesce(r.usage_name, '기타') not in ('기타', '')
    order by md5(r.result_id::text || %(seed)s) limit 1"""
_OPEN_SQL = """select i.item_id, i.sido, i.usage_name, i.appraisal_krw, i.min_price_krw, i.failed_count, i.sale_date
    from core.items i
    where i.sale_date >= current_date and i.appraisal_krw > 0 and i.min_price_krw > 0
      and i.min_price_krw < i.appraisal_krw and coalesce(i.failed_count, 0) >= 1
      and i.status_code is distinct from 'gone' and i.is_share is not true
      and coalesce(i.usage_name, '기타') not in ('기타', '')
    order by md5(i.item_id || %(seed)s) limit 1"""


def won(n: int) -> str:
    """3억 2,000만 원 꼴(만 원 아래는 버림)."""
    eok, man = divmod(int(n) // 10_000, 10_000)
    parts = ([f"{eok}억"] if eok else []) + ([f"{man:,}만"] if man else [])
    return (" ".join(parts) or "0") + " 원"


def _options(right: int, rnd: random.Random) -> tuple[list[str], int]:
    near = [d for d in (-20, -10, 10, 20) if 0 < right + d <= 200]
    picks = rnd.sample(near, 2)
    vals = [right, right + picks[0], right + picks[1]]
    rnd.shuffle(vals)
    return [f"{v}%" for v in vals], vals.index(right)


def today() -> dict[str, Any] | None:
    day = datetime.now(KST).date()
    seed = day.isoformat()
    rnd = random.Random(seed)
    with connect() as c:
        if day.toordinal() % 2 == 0:
            r = c.execute(_SOLD_SQL, {"seed": seed}).fetchone()
            if r:
                rate = round(r["winning_bid_krw"] * 100 / r["appraisal_krw"])
                opts, ans = _options(rate, rnd)
                return {
                    "kind": "rate",
                    "q": f"{r['sido']} {r['usage_name'] or ''} · 감정가 {won(r['appraisal_krw'])}인 물건이 "
                    f"{won(r['winning_bid_krw'])}에 낙찰됐어요. 낙찰가율은?",
                    "options": opts,
                    "answer": ans,
                    "why": f"{won(r['winning_bid_krw'])} ÷ {won(r['appraisal_krw'])} ≈ {rate}%예요. "
                    f"{r['sale_date']:%-m월 %-d일} 법원 결과예요.",
                    "item_id": r["item_id"],
                    "from": "w-price",
                }
        r = c.execute(_OPEN_SQL, {"seed": seed}).fetchone()
    if not r:
        return None
    pct = round(r["min_price_krw"] * 100 / r["appraisal_krw"])
    opts, ans = _options(pct, rnd)
    return {
        "kind": "start",
        "q": f"{r['sido']} {r['usage_name'] or ''} · 감정가 {won(r['appraisal_krw'])}, 유찰 {r['failed_count']}회, "
        f"이번 최저가 {won(r['min_price_krw'])}. 최저가는 감정가의 몇 %인가요?",
        "options": opts,
        "answer": ans,
        "why": f"{won(r['min_price_krw'])} ÷ {won(r['appraisal_krw'])} ≈ {pct}%예요. "
        f"매각기일은 {r['sale_date']:%-m월 %-d일}이에요.",
        "item_id": r["item_id"],
        "from": "w-price",
    }
