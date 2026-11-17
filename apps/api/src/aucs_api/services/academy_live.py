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


# 레벨4 실제 물건 판정(11/17): 법원 매각물건명세서 「매각으로 소멸되지 않는 권리」 칸을 그대로 보여 주고
# 떠안는지 고르게 함. 정답은 우리 분석이 아니라 법원이 그 칸에 쓴 말(「인수」 · 「말소동의」)에서만 냄 —
# 두 꼴이 섞인 글(다른 권리가 함께 적힘)이나 너무 긴 글은 문제로 쓰지 않음. 상세 원문이라 로그인한 회원에게만.
_JUDGE_SQL = """with c as (
      select i.item_id, i.case_id, i.item_no, i.sido, i.usage_name from core.items i
      where i.sale_date >= current_date and i.status_code is distinct from 'gone' and i.is_share is not true
      order by md5(i.item_id || %(seed)s) limit 3000)
    select c.item_id, c.sido, c.usage_name, k.keep
    from c
    cross join lateral (select payload from raw.court_doc_raw d
      where d.case_id = c.case_id and d.doc_kind = 'item_detail_' || coalesce(c.item_no, 1)
      order by d.fetched_at desc limit 1) d
    cross join lateral (select regexp_replace(
      coalesce(d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'ndstrcRghCtt', ''), '<br\\s*/?>', ' ', 'g') as keep) k
    where length(k.keep) between 20 and 220 and k.keep ~ %(pat)s and k.keep !~ %(not)s
    limit 1"""
_ASSUME = {"pat": r"매수인.{0,12}인수|인수함|인수됨", "not": r"말소\s*동의"}
_RELEASE = {"pat": r"말소\s*동의", "not": r"전세권|가등기|가처분|지상권|지역권|근저당|유치권|인수"}
JUDGE_OPTIONS = [
    "떠안는 것 없어요 — 낙찰로 모두 지워져요",
    "떠안을 수 있어요 — 내가 인수해요",
    "명세서로는 알 수 없어요",
]


def judge() -> dict[str, Any] | None:
    day = datetime.now(KST).date()
    seed = f"judge-{day.isoformat()}"
    release = day.toordinal() % 3 == 0  # 셋 중 하루는 「말소동의」(떠안지 않음), 나머지는 「인수」
    with connect() as c:
        r = c.execute(_JUDGE_SQL, {"seed": seed, **(_RELEASE if release else _ASSUME)}).fetchone()
        if not r and release:
            release = False
            r = c.execute(_JUDGE_SQL, {"seed": seed, **_ASSUME}).fetchone()
    if not r:
        return None
    keep = " ".join(r["keep"].split())
    why = (
        "보증기관이 등기를 지우는 데 동의했다는 확약서를 냈어요. 그래서 이 임차권등기는 낙찰로 지워지고 "
        "떠안지 않아요. 입찰 전에 명세서를 한 번 더 보세요."
        if release
        else "법원이 「매수인이 인수」라고 적었어요. 배당에서 다 받지 못한 보증금(또는 그 권리)은 낙찰자가 "
        "떠안아요 — 입찰가에서 그만큼 빼고 생각해야 해요."
    )
    return {
        "kind": "judge",
        "q": f"{r['sido']} {r['usage_name'] or ''} · 매각물건명세서 「매각으로 소멸되지 않는 권리」 칸: "
        f"“{keep}” — 낙찰받으면 어떻게 될까요?",
        "options": JUDGE_OPTIONS,
        "answer": 0 if release else 1,
        "why": why,
        "item_id": r["item_id"],
        "from": "a1-assume" if not release else "m1-base",
    }
