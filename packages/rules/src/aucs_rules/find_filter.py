"""찾기 조건(FIND-03) 한 곳(11/8 대표님 — 「같은 일은 한 길로」).

찾기 목록 · 전체 물건 표 · 홈 추천 · 모아 보기 · 조건 알림이 모두 이 조건으로 거름. 예전엔 API 두 곳과
수집기(알림)가 따로 적어 「API와 같게」를 손으로 맞췄고, 알림 쪽엔 공개·분석 끝 조건이 빠져 있었음.
순수 함수: SQL 조각과 값만 만듦(DB 없음). 경매 표 별칭 i(core.items) · c(core.cases) · a(최신 분석 결과),
공매 표 별칭 o(core.onbid_items). 공매 조각은 경매 조각과 같은 값 이름을 씀(court_where 의 값을 함께 넘김).
"""

from datetime import date
from typing import Any

VEHICLES = "자동차|중기|선박|항공기"  # 부동산만 다룸(10/28)

# 손님에게 보이는 경매 물건: 공개 · 부동산 · 법원 목록에 있음 · 분석이 끝남(10/18) · 입찰일이 지나지 않음
ANALYSIS_JOIN = (
    "left join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id"
    " order by version desc limit 1) a on true"
)
COURT_VISIBLE = (
    "i.display_policy = 'public' and i.sale_date >= %(today)s"
    f" and coalesce(i.usage_name, '') !~ '{VEHICLES}'"
    " and i.status_code is distinct from 'gone' and a.result is not null"
)
# 추천 점수(PICK-01)가 읽는 분석 칸 — 홈(그때 셈) · 모아 보기 · 수집기(미리 매김)가 같이 씀(11/14)
PICK_ANALYSIS_SQL = (
    "jsonb_build_object('market', a.result -> 'market', 'sale_rate', a.result -> 'sale_rate',"
    " 'court_cell', a.result -> 'court_cell', 'redev', a.result -> 'redev', 'new_item', a.result -> 'new_item',"
    " 'tenant_count', a.result -> 'tenant_count', 'signals', a.result -> 'signals', 'appraisal', a.result -> 'appraisal')"
)
# 임대 목적: 같은 단지(전용 ±3㎡) 1년 월세 가운데값 — 물건 상세 「세놓으면」과 같은 자료. ANALYSIS_JOIN 앞에 둠
RENT_JOIN = """left join lateral (
  select percentile_cont(0.5) within group (order by t.monthly_rent_krw)::bigint as monthly_krw,
         percentile_cont(0.5) within group (order by t.deposit_krw)::bigint as deposit_krw
  from core.trades t
  where t.region_code = left(i.region_code, 8) || '00' and t.lot_no = i.lot_no and t.deal_kind = 'lease'
    and t.monthly_rent_krw > 0 and t.deal_date >= %(today)s::date - 366
    and (i.building_area_m2 is null or abs(t.area_m2 - i.building_area_m2) <= 3)) rl on true
"""
HAS_PHOTO = "exists (select 1 from core.item_photos ph where ph.case_id = i.case_id)"

# 손님에게 보이는 공매 물건: 공개 · 진행 중 · 매각(임대 빼고) · 마감 전(마감 미정 포함)
ONBID_VISIBLE = (
    "o.display_policy = 'public' and o.status_code = 'active'"
    " and coalesce(o.disposal, '매각') like '%%매각%%' and (o.bid_end is null or o.bid_end >= now())"
)

USAGE_GROUPS = {
    "apt": "아파트",
    "villa": "다세대|연립|빌라",
    "officetel": "오피스텔",
    "house": "단독|다가구",
    "shop": "상가|근린|점포|사무|공장|창고|숙박|업무",
    "land": "대지|전답|임야|토지|잡종|^전$|^답$",
}
EXCLUDE_RULES = {
    "share": ["risk.share"],
    "special": ["risk.special_condition"],
    "villa": ["risk.neighborhood_villa"],
    "stop": ["risk.stop", "risk.withdraw"],
    "lien": ["risk.lien"],
    "senior": ["risk.senior_tenant", "risk.prior_rights", "risk.lease_reg"],
    "superficies": ["risk.superficies", "risk.land_right"],
    "illegal": ["risk.illegal"],
    "farmland": ["risk.farmland"],
    "resale": ["risk.resale"],
}
# 초보자 안전 모드: 한 번에 빼는 7가지(05 화면 설계)
SAFE_MODE = ["share", "lien", "senior", "superficies", "villa", "special", "stop"]

_NUM = (  # (조건 이름, 경매 칸, 공매 칸, 비교)
    ("failed_min", "i.failed_count", "o.failed_count", ">="),
    ("failed_max", "i.failed_count", "o.failed_count", "<="),
    ("app_min", "i.appraisal_krw", "o.appraisal_krw", ">="),
    ("app_max", "i.appraisal_krw", "o.appraisal_krw", "<="),
    ("price_max", "i.min_price_krw", "o.min_price_krw", "<="),
    ("area_min", "i.building_area_m2", "coalesce(o.building_m2, o.land_m2)", ">="),
    ("area_max", "i.building_area_m2", "coalesce(o.building_m2, o.land_m2)", "<="),
)


def kind_sql(col: str) -> str:
    """용도 칸 → 종류 SQL(CASE). 카드의 종류(pick.usage_kind)와 같은 표로 만듦(11/9 — 오피스텔로 찾으면 상가가 섞였음)."""
    from aucs_rules.pick import KIND_RULES

    whens = " ".join(
        f"when coalesce({col}, '') ~ '{'|'.join(words)}' then '{kind}'"
        for kind, words in KIND_RULES
    )
    return f"(case {whens} else 'etc' end)"


def usage_re(keys: list[str] | None) -> str | None:
    """고른 종류 → 용도 글자 정규식. 모르는 종류는 버림."""
    groups = [USAGE_GROUPS[g] for g in keys or [] if g in USAGE_GROUPS]
    return "|".join(f"({g})" for g in groups) if groups else None


def court_where(f: dict[str, Any], today: date) -> tuple[str, dict[str, Any]]:
    """조건 → 경매 표 SQL 조각(「 and …」)과 값. 값은 모두 바인딩(글자를 SQL에 넣지 않음)."""
    f = {k: v for k, v in f.items() if v not in (None, [], "")}
    sql = ""
    p: dict[str, Any] = {"today": today}
    if f.get("sido"):
        sql += " and i.sido = %(sido)s"
        p["sido"] = f["sido"]
    if f.get("sigungu"):
        sql += " and i.sigungu = any(%(sigungu)s)"
        p["sigungu"] = list(f["sigungu"])
    if f.get("max_cash"):
        # 가진 현금으로 살 수 있는 물건(11/9 대표님): 최저가에 낙찰받을 때 실제 필요한 현금
        # (낙찰가 − 대출 + 취득세·등기, 가진 집 수별 — 분석이 calc.cash_at_min 으로 적어 둠).
        # 아직 분석에 없는 물건은 예전 기준(입찰보증금 = 최저가의 10%)으로.
        sql += (
            " and coalesce((a.result -> 'cash_need' ->> %(homes_key)s)::bigint,"
            " i.min_price_krw / 10) <= %(max_cash)s"
        )
        p["max_cash"] = int(f["max_cash"])
        p["homes_key"] = str(min(2, max(0, int(f.get("homes") or 0))))
    if f.get("court"):
        sql += " and c.court_code = any(%(court)s)"
        p["court"] = list(f["court"])
    if ure := usage_re(f.get("usage")):
        sql += f" and {kind_sql('i.usage_name')} = any(%(kinds)s)"
        p["kinds"] = [k for k in f["usage"] if k in USAGE_GROUPS]
        p["usage_re"] = ure  # 공매 조건(onbid_where)이 같이 씀
    for key, col, _, op in _NUM:
        if f.get(key) is not None:
            sql += f" and coalesce({col}, 0) {op} %({key})s"
            p[key] = f[key]
    if f.get("rate_max") is not None:
        sql += " and i.min_price_krw * 100 <= %(rate_max)s * i.appraisal_krw"
        p["rate_max"] = f["rate_max"]
    if f.get("days_max") is not None:
        sql += " and i.sale_date <= %(today)s + %(days_max)s"
        p["days_max"] = int(f["days_max"])
    rules = [r for k in f.get("exclude") or [] for r in EXCLUDE_RULES.get(k, [])]
    if rules:
        sql += """ and not exists (select 1 from jsonb_array_elements(coalesce(a.result -> 'signals', '[]'::jsonb)) s
                   where s ->> 'rule_id' = any(%(ex_rules)s) and s ->> 'status' <> '모름')"""
        p["ex_rules"] = rules
    if "fatal" in (f.get("exclude") or []):
        sql += """ and not exists (select 1 from jsonb_array_elements(coalesce(a.result -> 'signals', '[]'::jsonb)) s
                   where s ->> 'level' = 'fatal')"""
    if f.get("q"):
        sql += (
            " and (i.address ilike %(q)s or i.building_desc ilike %(q)s or c.case_no ilike %(q)s)"
        )
        p["q"] = f"%{str(f['q']).strip()}%"
    return sql, p


def onbid_where(f: dict[str, Any]) -> str | None:
    """같은 조건을 공매 표에 맞춘 SQL 조각 — 값은 court_where 가 만든 것을 그대로 씀.
    경매만 보거나 법원을 고르면 None."""
    f = {k: v for k, v in f.items() if v not in (None, [], "")}
    if f.get("source") == "court" or f.get("court"):
        return None
    sql = ""
    if f.get("sido"):
        sql += " and o.sido = %(sido)s"
    if f.get("sigungu"):  # 경기도는 시군구 칸이 「수원시 영통구」처럼 구까지 옴 → 시 이름도 통과
        sql += " and (o.sigungu = any(%(sigungu)s) or split_part(o.sigungu, ' ', 1) = any(%(sigungu)s))"
    if f.get("max_cash"):
        sql += " and o.min_price_krw / 10 <= %(max_cash)s"
    if usage_re(f.get("usage")):
        sql += " and coalesce(o.usage_name, '') || ' ' || coalesce(o.title, '') ~ %(usage_re)s"
    for key, _, col, op in _NUM:
        if f.get(key) is not None:
            sql += f" and coalesce({col}, 0) {op} %({key})s"
    if f.get("rate_max") is not None:
        sql += " and o.min_price_krw * 100 <= %(rate_max)s * o.appraisal_krw"
    if f.get("days_max") is not None:
        sql += " and (o.bid_end at time zone 'Asia/Seoul')::date <= %(today)s + %(days_max)s"
    if f.get("exclude"):
        sql += " and o.kind <> 'trust'"  # 신탁은 판정을 못 해 위험을 뺄 때 함께 뺌
    if f.get("q"):
        sql += " and (o.address ilike %(q)s or o.title ilike %(q)s or o.mng_no ilike %(q)s)"
    return sql
