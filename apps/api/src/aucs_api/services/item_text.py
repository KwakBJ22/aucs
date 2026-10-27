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


def failure_table(signals: list[dict[str, Any]]) -> list[dict[str, str]]:
    """PC 전문가 보기: 실패 11유형 전체와 이 물건 상태(걸림·확인 필요·신호 없음). 신호 없음 ≠ 안전."""
    out = []
    for code, title in FAILURE_TYPES.items():
        mine = [s for s in signals if s.get("ftype") == code]
        hit = [
            s
            for s in mine
            if s.get("level") in ("fatal", "high", "mid")
            and s.get("status") not in ("모름", "확인 필요")
        ]
        if hit:
            state, why = "걸림", hit[0]["title"]
        elif mine:
            state, why = "확인 필요", mine[0]["title"]
        else:
            state, why = "신호 없음", ""
        out.append({"code": code, "title": title, "state": state, "why": why})
    return out


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
