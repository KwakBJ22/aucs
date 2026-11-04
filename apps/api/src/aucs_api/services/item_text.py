"""상세 화면 문구: 매각 결과 이름·자료 태그·실패 11유형 표·맨 위 한 줄 판정"""

from typing import Any

from aucs_rules.risk import FAILURE_TYPES

RESULT_KO = {
    "scheduled": "예정",
    "sold": "매각",
    "failed": "유찰",
    "changed": "변경",
    "withdrawn": "취하",
    "unknown": "모름",
}


TAGS = [
    ("status_report", "현황조사"),
    ("spec_sheet", "명세서"),
    ("deliveries", "문건"),
    ("registry", "등기부"),
    ("building", "건축물대장"),
]


_HOUSING = ("아파트", "다세대", "연립", "빌라", "단독", "다가구", "주택")
_PERMIT = ("전", "답", "과수원", "농지", "학교", "의료", "사회복지", "종교")
# 유형마다 「무엇을 받아야 확인되나」(11/4 — 신호 없음 한 가지에 해당 없음·확인함·자료 없음이 섞여 있었음)
_NEED = {
    "T1": ("status_report", "현황조사"),
    "T2": ("deliveries", "문건송달"),
    "T3": ("status_report", "현황조사"),
    "T4": ("deliveries", "문건송달"),
    "T5": ("deliveries", "문건송달"),
    "T8": ("building", "건축물대장"),
    "T10": ("building", "건축물대장"),
}
_OK = ("extracted", "verified", "fetched")


def _not_applicable(code: str, usage: str, redev: bool) -> bool:
    """이 물건에는 생길 수 없는 유형."""
    u = usage or ""
    land_only = bool(u) and all(k in ("대지", "임야", "전", "답", "전답", "잡종지", "토지") for k in
                                (w.strip() for w in u.replace("/", ",").split(",")))  # fmt: skip
    if land_only and code in ("T3", "T10"):  # 건물이 없는 땅 — 상가 임차인·위반건축물 없음
        return True
    if code == "T3":  # 상가 임차인 보증금 한도 — 주거용이면 해당 없음
        return any(k in u for k in _HOUSING) and not any(k in u for k in ("근린", "상가"))
    if code == "T7":  # 재개발·재건축 조합원 자격 — 구역 밖이면 해당 없음
        return not redev
    if code == "T9":  # 허가·자격이 필요한 물건(농지·학교 등)
        words = {w.strip() for w in u.replace("/", ",").split(",")}
        return not (words & {"전", "답", "전답"} or any(k in u for k in _PERMIT[2:]))
    return False


def failure_table(
    signals: list[dict[str, Any]], facts: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """실패 11유형 전체와 이 물건 상태(11/4 다섯 가지).

    걸림 · 확인 필요(원문 읽기) · 확인함(자료를 받았고 신호 없음) · 해당 없음 · 자료 기다림(무엇이 오면 확인되나).
    T6 입찰표 실수는 입찰표 검사가 막으므로 「대비됨」, T11 값어치·대출은 시세가 있으면 계산에서 확인.
    """
    f = facts or {}
    ds = f.get("ds") or {}
    usage, redev, market = f.get("usage") or "", bool(f.get("redev")), bool(f.get("market"))
    out = []
    for code, title in FAILURE_TYPES.items():
        mine = [s for s in signals if s.get("ftype") == code]
        known = [s for s in mine if s.get("status") != "모름"]
        hit = [
            s
            for s in known
            if s.get("level") in ("fatal", "high", "mid") and s.get("status") != "확인 필요"
        ]
        need = _NEED.get(code)
        if hit:
            state, why = "걸림", hit[0]["title"]
        elif known:
            state, why = "확인 필요", known[0]["title"]
        elif _not_applicable(code, usage, redev):
            state, why = "해당 없음", ""
        elif code == "T6":
            state, why = "대비됨", "입찰표 검사가 금액·자릿수를 막아 드려요"
        elif code == "T11":
            state, why = (
                ("확인함", "계산에서 시세·대출로 셈해요")
                if market
                else ("자료 기다림", "시세가 들어오면 확인돼요")
            )
        elif code == "T7":
            state, why = "확인함", ""
        elif (
            need
            and ds.get(need[0]) not in _OK
            and not (need[0] == "status_report" and ds.get("spec_sheet") in _OK and code == "T3")
        ):
            state, why = (
                "자료 기다림",
                f"{need[1]}{'를' if need[1].endswith('사') else '을'} 받으면 확인돼요",
            )
        else:
            state, why = "확인함", ""
        out.append({"code": code, "title": title, "state": state, "why": why})
    return out  # fmt: skip


PENDING = "오늘 오후 분석이 끝나면 보여요"


GONE_LINE = "법원 목록에서 빠졌어요 · 기일 변경이나 취하일 수 있어요 · 법원에서 확인하세요"


def verdict(signals: list[dict[str, Any]], n_check: int | None = None) -> str:
    """맨 위 한 줄 판정. 치명 > 주의 > 모름 > 문제 없음.

    n_check: 「무엇을 확인하나」의 남은 확인 수 — 주면 그 수를 씀(두 곳 숫자가 어긋나지 않게, 10/19 점검)."""
    fatal = [s for s in signals if s.get("level") == "fatal"]
    if fatal:
        return f"{fatal[0]['title']} — 초보자는 피하는 게 좋아요"
    warn = [s for s in signals if s.get("level") in ("high", "mid") and s.get("status") != "모름"]
    n = len([s for s in signals if s.get("status") == "모름"]) if n_check is None else n_check
    if warn:
        return f"{warn[0]['title']}" + (f" · 확인할 것 {n}가지" if n else "")
    if n:
        return f"큰 문제 신호는 없어요. 확인할 것 {n}가지만 보면 돼요"
    return "큰 문제 신호는 없어요"
