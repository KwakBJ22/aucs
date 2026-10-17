"""진행 판단: 정지·회생 신청과 속행 신청의 선후로 기일이 바뀔 수 있는지 봅니다 (04탭 11절)."""

from datetime import date

from aucs_rules.result import RuleResult, Status


def judge_progress(events: list[tuple[date, str]]) -> RuleResult:
    """events: (날짜, 문건 분류) 목록."""
    stops = [d for d, c in events if c in ("회생·파산", "정지·취하 시도")]
    goes = [d for d, c in events if c == "경매 속행 신청"]
    if not stops:
        return RuleResult(None, Status.ESTIMATED, "progress.none", [])
    last_stop, last_go = max(stops), max(goes) if goes else None
    ev = [{"last_stop": str(last_stop), "last_go": str(last_go) if last_go else None}]
    if last_go is None or last_stop > last_go:
        return RuleResult("기일이 바뀔 수 있음", Status.ESTIMATED, "progress.may_change", ev)
    return RuleResult("속행 신청됨", Status.ESTIMATED, "progress.resumed", ev)
