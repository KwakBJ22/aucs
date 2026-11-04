"""소액임차 최우선변제 지역 구분 (주택임대차보호법 시행령 제10조, 수도권정비계획법 시행령 별표1).

구분: seoul / overcrowded(과밀억제권역, 서울 제외) / metro(광역시급) / other.
기준일은 「최초 담보물권 설정일」 — 그날 시행 중인 구분을 씁니다.
일부 동만 과밀억제권역인 시(남양주·시흥)는 동으로 가리고, 모르면 「확인 필요」.
개발 기준이며 3단계 법률 검토 대상입니다. 서울·경기·인천만 다룹니다(우리 수집 범위, 인천은 11/4 더함).
"""

from datetime import date

from aucs_rules.result import RuleResult, Status

# 경기도 과밀억제권역 (서울 제외)
_OVERCROWDED = {
    "의정부시",
    "구리시",
    "하남시",
    "고양시",
    "수원시",
    "성남시",
    "안양시",
    "부천시",
    "광명시",
    "과천시",
    "의왕시",
    "군포시",
}
_NAMYANGJU_OVERCROWDED_DONGS = {
    "호평동",
    "평내동",
    "금곡동",
    "일패동",
    "이패동",
    "삼패동",
    "가운동",
    "수석동",
    "지금동",
    "도농동",
}
# 시행령 개정마다 과밀억제권역 구분에 더한 곳 / 광역시급에 더한 곳
_PERIODS = [
    (date(2018, 9, 18), {"용인시", "화성시"}, {"안산시", "김포시", "광주시", "파주시"}),
    (
        date(2021, 5, 11),
        {"용인시", "화성시", "김포시"},
        {"안산시", "광주시", "파주시", "이천시", "평택시"},
    ),
]


def region_class(
    sido: str | None,
    sigungu: str | None,
    dong: str | None,
    base_date: date,
    overcrowded_hint: bool | None = None,
) -> RuleResult:
    """(구분, 확실한 정도). 2018-09-18 전 설정은 이 표에 없어 「모름」.

    overcrowded_hint(11/4): 감정평가 요항 「토지 이용 계획」에 「과밀억제권역」이 있으면 True,
    요항은 있는데 그 말이 없으면 False, 요항이 없으면 None — 동으로 못 가리는 곳(남양주·시흥·인천)을 이것으로 가림.
    """
    if sido == "서울특별시":
        return RuleResult("seoul", Status.ESTIMATED, "small_region.seoul", [])
    if sido == "인천광역시" and sigungu:
        ev0 = [{"sigungu": sigungu, "hint": overcrowded_hint}]
        if sigungu in ("강화군", "옹진군"):  # 광역시의 군 — 「그 밖의 지역」
            return RuleResult("other", Status.ESTIMATED, "small_region.incheon", ev0)
        if overcrowded_hint is True:
            return RuleResult("overcrowded", Status.ESTIMATED, "small_region.incheon", ev0)
        if overcrowded_hint is False:  # 경제자유구역·남동국가산업단지 등 — 광역시 구분
            return RuleResult("metro", Status.NEEDS_CHECK, "small_region.incheon", ev0)
        return RuleResult("overcrowded", Status.NEEDS_CHECK, "small_region.incheon", ev0)
    if sido != "경기도" or not sigungu:
        return RuleResult(None, Status.UNKNOWN, "small_region.out_of_scope", [{"sido": sido}])
    periods = [p for p in _PERIODS if p[0] <= base_date]
    if not periods:
        return RuleResult(
            None, Status.UNKNOWN, "small_region.too_old", [{"base_date": str(base_date)}]
        )
    _, extra_over, extra_metro = periods[-1]
    ev = [{"sigungu": sigungu, "dong": dong, "period_from": str(periods[-1][0])}]
    if sigungu in _OVERCROWDED or sigungu in extra_over:
        return RuleResult("overcrowded", Status.ESTIMATED, "small_region.overcrowded", ev)
    if sigungu in ("남양주시", "시흥시") and overcrowded_hint is not None:
        cls = "overcrowded" if overcrowded_hint else "other"
        return RuleResult(cls, Status.ESTIMATED, "small_region.by_appraisal", ev)
    if sigungu == "남양주시":
        if not dong:
            return RuleResult(None, Status.NEEDS_CHECK, "small_region.namyangju", ev)
        cls = "overcrowded" if dong in _NAMYANGJU_OVERCROWDED_DONGS else "other"
        return RuleResult(cls, Status.ESTIMATED, "small_region.namyangju", ev)
    if sigungu == "시흥시":
        # 반월특수지역(일부)은 과밀억제권역에서 빠짐 — 동만으로 가리기 어려워 확인 필요
        return RuleResult("overcrowded", Status.NEEDS_CHECK, "small_region.siheung", ev)
    if sigungu in extra_metro:
        return RuleResult("metro", Status.ESTIMATED, "small_region.metro", ev)
    return RuleResult("other", Status.ESTIMATED, "small_region.other", ev)
