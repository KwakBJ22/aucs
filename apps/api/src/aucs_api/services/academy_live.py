"""아카데미 레벨4 실제 물건 판정(11/17) — 법원 매각물건명세서 원문으로 하루 한 문제.

「오늘의 물건 문제」(낙찰가율 · 최저가 % 셈)는 11/23 대표님 결정으로 뺌 — 산수만 하는 문제라 뜻이 없었음.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from aucs_api.db import connect

KST = timezone(timedelta(hours=9))


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
        and jsonb_typeof(d.payload->'dma_result') = 'object'
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
