"""ITEM-06 「무엇을 확인하나」: 자료 상태로 만드는 체크리스트와 사건 흐름 막대 (순수 함수).

확인 상태 4가지(04탭): 확인 완료 / 미확인(안전으로 보지 않음) / 자료 충돌 / 전문가 확인 필요.
항목마다 근거 문서 이름과 우리가 받은 시각을 붙입니다.
"""

from datetime import date, datetime
from typing import Any

DONE, UNKNOWN, CONFLICT, EXPERT = "확인 완료", "미확인", "자료 충돌", "전문가 확인 필요"
OK_STATUS = ("extracted", "verified", "fetched")

# (자료 종류, 항목 이름, 무엇을 보는지, 미확인일 때 안내)
DOC_ITEMS = [
    ("status_report", "임차인", "누가 살고 있는지 · 전입일 · 보증금", "현황조사서는 매각기일 2주 전쯤 법원에 올라와요"),
    ("spec_sheet", "떠안는 권리", "매각물건명세서의 인수 권리 · 비고란 조건", "명세서는 매각기일 1주 전에 공개돼요"),
    ("deliveries", "사건 문건", "배당요구 · 권리신고 · 정지 신청", "법원 문건 목록을 아직 못 받았어요"),
    ("registry", "등기부", "말소기준 · 근저당 · 가압류", "「무엇을 떠안나」에서 등기부 PDF를 올리면 읽어 드려요"),
    ("building", "건축물대장", "위반건축물 · 실제 용도", "아직 못 받았어요"),
]  # fmt: skip
DOC_NAME = {
    "status_report": "현황조사서",
    "spec_sheet": "매각물건명세서",
    "deliveries": "문건·송달내역",
    "registry": "등기부",
    "building": "건축물대장",
}
SELF_ITEMS = [
    ("move_in", "전입세대 열람", "숨은 임차인이 없는지 — 주민센터에서 직접 떼야 해요"),
    ("site", "현장 확인", "점유 상태 · 관리비 체납 · 건물 상태"),
]


def _ts(v: Any) -> str | None:
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    return str(v) if v else None


def build_checklist(
    data_status: dict[str, str],
    doc_times: dict[str, Any],
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """자료 상태 + 신호 → 체크리스트. 끝나지 않은 것이 앞에 옵니다."""
    conflict = any(s.get("rule_id") == "risk.conflict" for s in signals)
    out: list[dict[str, Any]] = []
    for kind, label, what, hint in DOC_ITEMS:
        ok = data_status.get(kind) in OK_STATUS
        state = DONE if ok else UNKNOWN
        if kind == "status_report" and conflict:
            state = CONFLICT
        out.append({
            "key": kind, "label": label, "what": what, "state": state,
            "hint": None if ok else hint,
            "evidence": {"doc": DOC_NAME[kind], "fetched_at": _ts(doc_times.get(kind))} if ok else None,
        })  # fmt: skip
    for s in signals:
        if s.get("status") == "확인 필요" and s.get("rule_id") != "risk.conflict":
            out.append({
                "key": s["rule_id"], "label": s["title"].split(" — ")[0], "what": s["title"],
                "state": EXPERT, "hint": None, "evidence": None,
            })  # fmt: skip
    for key, label, what in SELF_ITEMS:
        out.append(
            {
                "key": key,
                "label": label,
                "what": what,
                "state": UNKNOWN,
                "hint": None,
                "evidence": None,
            }
        )
    order = {CONFLICT: 0, EXPERT: 1, UNKNOWN: 2, DONE: 3}
    return sorted(out, key=lambda x: order[x["state"]])


def build_flow(
    *,
    events: list[dict[str, Any]],
    claim_deadline: date | None,
    rounds: list[dict[str, Any]],
    sale_date: date | None,
    schedule_rows: list[dict[str, Any]],
    today: date,
    failed_count: int | None = None,
) -> list[dict[str, Any]]:
    """사건 흐름 막대: 경매 시작 → 배당요구종기 → 첫 매각기일 → 이번 매각기일 → 매각결정 → 잔금 → 배당.

    지난 단계는 실제 날짜, 앞 단계는 예상일(estimated=True). 모르는 날짜는 None.
    """
    ev_dates = sorted(str(e["date"]) for e in events if e.get("date"))
    first_round = rounds[0]["sale_date"] if rounds else None
    if failed_count and first_round == sale_date:  # 유찰이 있었는데 앞 회차 기록이 없으면 모름
        first_round = None
    sched = {r["key"]: r["start"] for r in schedule_rows}

    def iso(d: Any) -> str | None:
        return d.isoformat() if isinstance(d, date) else (str(d) if d else None)

    steps = [
        ("start", "경매 시작", ev_dates[0] if ev_dates else None, False),
        ("claim", "배당요구종기", iso(claim_deadline), False),
        ("first", "첫 매각기일", iso(first_round), False),
        ("now", "이번 매각기일", iso(sale_date), False),
        ("decide", "매각결정", sched.get("decide"), True),
        ("pay", "잔금", sched.get("pay"), True),
        ("dividend", "배당", sched.get("dividend"), True),
    ]
    t = today.isoformat()
    return [
        {
            "key": k,
            "label": label,
            "date": d,
            "estimated": est,
            "done": bool(d and d <= t and not est),
        }
        for k, label, d, est in steps
    ]
