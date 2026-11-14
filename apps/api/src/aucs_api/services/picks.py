"""홈 「오늘의 추천」·「마감 임박」·「기다리면 더 싸질 물건」(11/4 대표님).

점수는 규칙 PICK-01(packages/rules/pick.py) 하나로 — 분석 결과(매일 아침 갱신)에서 그때 셈하므로 그날은 누구에게나 같은 값.
11/7 대표님: 사진 없는 물건은 홈 세 칸 어디에도 띄우지 않음(법원은 입찰 2주 전쯤 사진을 올림).
- 추천: 공고된 물건은 입찰 14일 안(1~14일) + 유찰 뒤 다음 회차(공고 전, 30일 안 — 지난 회차 사진이 있음) ·
  점수 순 · 같은 단지 1건·같은 구 2건까지
- 마감 임박: 7일 안 · 점수 70 이상만 짧게
- 기다리면 더 싸질 물건: ① 유찰 뒤 다음 기일이 잡힌 물건(공고 전, status_code='preview') ② 같은 법원·종류·
  회차 물건의 최근 6개월 실제 유찰 비율이 70% 넘는 물건(WAIT-01, 11/7) — 「10건 중 9건 유찰 · 유찰되면 ○○원부터」
"""

from datetime import date, datetime, timedelta
from typing import Any

import psycopg
from aucs_rules.find_filter import (
    ANALYSIS_JOIN,
    COURT_VISIBLE,
    HAS_PHOTO,
    PICK_ANALYSIS_SQL,
    RENT_JOIN,
    court_where,
)
from aucs_rules.pick import case_key, diversify, score_row
from aucs_rules.wait import PREVIEW, next_round

from aucs_api.cache import memo
from aucs_api.db import batch, connect
from aucs_api.services.fail_odds import fail_stats
from aucs_api.services.items import _CARD_SQL, add_cols, add_join, card

# 추천 · 모아 보기가 읽는 칸: 카드 + 점수 재료(분석 칸) + 다음 회차 판단에 쓰는 칸
_SQL = add_cols(_CARD_SQL, f"{PICK_ANALYSIS_SQL} as analysis, i.is_special_case, i.status_code")
# 공고 전 다음 회차는 「법원 목록에서 빠짐」과 다름 — _CARD_SQL 의 gone 걸러내기는 그대로 둠

# 미리 매겨 둔 점수(analysis.pick_scores — 수집기 jobs/pick_scores 가 분석 뒤마다 다시 채움, 11/14)에서 읽는 길.
# 예전엔 홈을 열 때마다 물건 4,000줄을 받아 서버에서 점수를 매겨, 기억해 둔 것이 없으면 10초쯤 걸렸음.
_TABLE_SQL = add_cols(
    _CARD_SQL,
    "i.status_code, ps.score, ps.reasons, ps.likely_fail, ps.fail_odds, ps.next_min_krw",
).replace(
    "join core.cases c using (case_id)",
    "join core.cases c using (case_id)\n"
    "join analysis.pick_scores ps on ps.item_id = i.item_id and ps.purpose = %(pp)s",
    1,
)
# 먼저 가벼운 줄(번호 · 점수 · 날짜 · 추리는 데 쓰는 칸)만 받아 세 칸을 고르고, 고른 물건(스무 건 안쪽)만 카드 칸을 받음.
# 11/14 배포 뒤 잼: 칸마다 카드 칸까지 300줄씩 받으면 분석 글을 물건마다 풀어 한 번에 1초씩(세 번 3초) → 가벼운 줄은 0.1초
_LIGHT_SQL = f"""
select i.item_id, i.sale_date, i.status_code, c.court_code, c.case_no, i.sigungu, i.gu,
       i.building_desc, ps.score, ps.likely_fail
from core.items i
join core.cases c using (case_id)
join analysis.pick_scores ps on ps.item_id = i.item_id and ps.purpose = %(pp)s
{ANALYSIS_JOIN}
where {COURT_VISIBLE} and {HAS_PHOTO}"""
_FRESH_HOURS = 36  # 이보다 오래된 점수면 안 씀(수집기가 멈춘 것) → 그때 셈으로


def _pick_window(x: dict[str, Any]) -> bool:
    """추천 칸에 넣을 때(11/7): 공고된 물건 입찰 1~14일 남음, 유찰 뒤 다음 회차는 30일 안."""
    d = x["d_day"] if x["d_day"] is not None else -1
    return 1 <= d <= 30 if x["preview"] else 1 <= d <= 14


@memo(ttl=3600, size=4)
def reduction_table(today: date) -> dict[str, Any]:
    """법원별 유찰 때 깎는 비율(기준표 court_reduction_pct) — 홈 추천·모아 보기·물건 상세가 같이 씀(11/8)."""
    with connect() as c:
        red = c.execute(
            "select value from ref.rule_tables where rule_key = 'court_reduction_pct'"
            " and valid_from <= %s order by valid_from desc limit 1",
            (today,),
        ).fetchone()
    return dict((red or {}).get("value") or {})


def mark_next_round(
    cd: dict[str, Any], r: dict[str, Any], reduction: dict[str, Any], today: date
) -> None:
    """「기다리면 더 싸질 물건」 표시를 카드에 — 판단은 규칙 wait.next_round 한 곳(WAIT-01)."""
    cd.update(next_round(r, fail_stats(today), reduction, today))


def _split(scored: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """칸마다 점수 순 후보 → 같은 단지 1 · 같은 구 2건까지, 앞 칸에 나온 사건은 다음 칸에 또 안 나오게(11/9)."""
    picks = diversify(scored[0], 8)
    seen = {case_key(x) for x in picks}
    soon = diversify(scored[1], 4, skip_cases=seen)
    seen |= {case_key(x) for x in soon}
    nxt = diversify(scored[2], 6, skip_cases=seen)
    return {"picks": picks, "soon": soon, "next": nxt}


def light_card(r: dict[str, Any], today: date) -> dict[str, Any]:
    """가벼운 줄 → 추릴 때(diversify · case_key) 쓰는 칸만 든 것. 칸 이름은 카드와 같게."""
    return {
        "item_id": r["item_id"],
        "court": r["court_code"],
        "case_no": r["case_no"],
        "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x),
        "building": r["building_desc"],
        "d_day": (r["sale_date"] - today).days if r["sale_date"] else None,
    }


def _from_table(more: str, params: dict[str, Any], purpose: str | None, today: date) -> dict[str, Any] | None:  # fmt: skip
    """미리 매겨 둔 점수로 세 칸. 표가 없거나 비었거나 오래됐으면 None(→ 그때 셈)."""
    p = {**params, "pp": purpose or ""}
    try:
        with connect() as c:
            q_at, q_rows = batch(
                c,
                [
                    (
                        "select max(computed_at) as at from analysis.pick_scores where purpose = %(pp)s",
                        p,
                    ),
                    (_LIGHT_SQL + more + " order by ps.score desc, i.item_id", p),
                ],
            )
            at = (q_at.fetchone() or {}).get("at")
            if not at or datetime.now(at.tzinfo) - at > timedelta(hours=_FRESH_HOURS):
                return None
            light = []
            for r in q_rows.fetchall():
                x = light_card(r, today)
                x.update(score=r["score"], preview=r["status_code"] == PREVIEW, likely_fail=r["likely_fail"])  # fmt: skip
                light.append(x)
            got = _split(
                [
                    [x for x in light if _pick_window(x)],
                    [x for x in light if 0 <= (x["d_day"] or 0) <= 7 and x["score"] >= 70],
                    [x for x in light if x["preview"] or x["likely_fail"]],
                ]
            )
            ids = [x["item_id"] for v in got.values() for x in v]
            rows = (
                c.execute(
                    _TABLE_SQL + " and i.item_id = any(%(ids)s)", {**p, "ids": ids}
                ).fetchall()
                if ids
                else []
            )
    except psycopg.Error:  # 표가 아직 없음(이주 0052 전) 등
        return None
    cards: dict[str, dict[str, Any]] = {}
    for r in rows:
        cd = card(r, today)
        cd.update(score=r["score"], reasons=r["reasons"], preview=r["status_code"] == PREVIEW,
                  fail_odds=r["fail_odds"], likely_fail=r["likely_fail"])  # fmt: skip
        if r["next_min_krw"]:
            cd["next_min_krw"] = r["next_min_krw"]
        cards[r["item_id"]] = cd
    return {k: [cards[x["item_id"]] for x in v if x["item_id"] in cards] for k, v in got.items()}


def home_picks(
    *, sigungu: list[str], max_cash: int | None, purpose: str | None, today: date, homes: int = 0
) -> dict[str, Any]:
    """내 지역·현금 안 물건을 PICK-01 로 매겨 세 칸으로 나눔. purpose 가 없으면(로그인 전) 목적 점수 없이 점수 큰 것 위주."""
    if purpose == "resell":  # 시작 질문 「매도(되팔기)」 = 규칙의 투자 목적
        purpose = "invest"
    params: dict[str, Any] = {"today": today}
    more, fp = court_where(
        {"sigungu": sigungu, "max_cash": max_cash, "homes": homes}, today
    )  # 찾기와 같은 규칙(FIND-03)
    params.update(fp)
    got = _from_table(more, params, purpose, today)
    if got is not None:
        return got

    # ── 그때 셈(미리 매겨 둔 점수가 없을 때만): 물건 줄을 받아 여기서 점수를 매김
    sql = _SQL
    if purpose == "rent":  # 임대 목적만 월세 가운데값
        sql = add_join(
            add_cols(sql, "rl.monthly_krw as rent_monthly, rl.deposit_krw as rent_deposit"),
            RENT_JOIN,
        )
    # 사진 없는 물건은 어차피 안 띄움(11/7) — DB 에서 먼저 걸러 받는 줄을 줄임
    sql += more + f" and {HAS_PHOTO} order by i.sale_date limit 4000"
    with connect() as c:
        rows = c.execute(sql, params).fetchall()
    reduction = reduction_table(today)

    scored: list[dict[str, Any]] = []
    for r in rows:
        if not r["photo"]:
            continue
        p = score_row(r, purpose, today)
        if p["excluded"]:
            continue
        cd = card(r, today)
        cd["score"] = p["score"]
        cd["reasons"] = p["reasons"]
        mark_next_round(cd, r, reduction, today)
        scored.append(cd)
    scored.sort(key=lambda x: -x["score"])
    return _split(
        [
            [x for x in scored if _pick_window(x)],
            [x for x in scored if 0 <= (x["d_day"] or 0) <= 7 and x["score"] >= 70],
            [x for x in scored if x["preview"] or x["likely_fail"]],
        ]
    )
