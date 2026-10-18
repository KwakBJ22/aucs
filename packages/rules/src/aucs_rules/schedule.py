"""낙찰 후 일정표 (SCHED-01, 04탭 9절).

법정 기간은 조문대로(말일이 토·일·공휴일이면 다음 영업일 — 민법 §161), 실무 기간은 범위(추정).
공휴일은 인자로 받습니다(ref.holidays 중 확인된 날만). 넣지 않은 공휴일이 있으면 마감이 실제보다
앞서 보일 뿐 늦게 보이지는 않도록, 확인 안 된 날은 넣지 않습니다.
"""

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from aucs_rules.result import RuleResult, Status

WD = "월화수목금토일"


@dataclass(frozen=True)
class Cal:
    """영업일 달력."""

    holidays: frozenset[date]

    def is_biz(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def next_biz(self, d: date) -> date:
        while not self.is_biz(d):
            d += timedelta(days=1)
        return d

    def prev_biz(self, d: date) -> date:
        while not self.is_biz(d):
            d -= timedelta(days=1)
        return d


def add_months(d: date, m: int) -> date:
    """m개월 뒤 같은 날(없으면 그 달 말일)."""
    y, mo = divmod(d.month - 1 + m, 12)
    y, mo = d.year + y, mo + 1
    return date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def fmt(d: date) -> str:
    """2026-11-17(화)."""
    return f"{d.isoformat()}({WD[d.weekday()]})"


def short(d: date) -> str:
    """11/17(화) — 휴대폰 한 줄용."""
    return f"{d.month}/{d.day}({WD[d.weekday()]})"


def _row(
    key: str,
    label: str,
    todo: str,
    basis: str,
    a: date,
    b: date | None = None,
    *,
    legal: bool = False,
    deadline: bool = False,
) -> dict[str, Any]:
    b = b or a
    return {
        "key": key, "label": label, "todo": todo, "basis": basis,
        "start": a.isoformat(), "end": b.isoformat(),
        "text": fmt(a) if a == b else f"{fmt(a)} ~ {fmt(b)}",
        "short": short(a) if a == b else f"{short(a)} ~ {short(b)}",
        "status": Status.CONFIRMED.value if legal else Status.ESTIMATED.value,
        "deadline": deadline,
    }  # fmt: skip


def after_sale(
    sale_date: date,
    holidays: Iterable[date],
    *,
    pay_date: date | None = None,
    flags: Iterable[str] = (),
) -> RuleResult:
    """매각기일(낙찰일)부터 인도명령 마감까지 실제 날짜 일정.

    pay_date가 없으면 보통 경우(허가 확정 + 3주)로 잡고 status를 「추정」으로.
    flags: farmland(농취증) · special_corp(주무관청 허가) · tenant_paid(배당받는 임차인) ·
           tenant_unpaid(배당 못 받는 대항력 임차인·유치권) — 해당될 때만 줄을 더합니다.
    """
    cal = Cal(frozenset(holidays))
    fl = set(flags)
    d0 = sale_date
    rows: list[dict[str, Any]] = []
    add = rows.append

    add(
        _row(
            "sale", "매각기일(낙찰)", "보증금 영수증 받기 · 사건기록 열람 · 대출 상담 시작", "—", d0
        )
    )
    if "farmland" in fl:
        add(_row("farmland", "농취증 신청 시작", "매각결정기일 전까지 못 내면 불허가·보증금 몰수",
                 "농지법 §8 · 실무", d0, deadline=True))  # fmt: skip
    if "special_corp" in fl:
        add(_row("permit", "주무관청 처분허가서", "채무자만 신청 가능 — 매각결정기일 전까지 없으면 불허가·몰수",
                 "실무", d0, deadline=True))  # fmt: skip
    decide = cal.prev_biz(d0 + timedelta(days=7))  # 「1주 이내」 → 휴일이면 앞당겨짐
    add(
        _row(
            "decide",
            "매각결정기일",
            "허가 여부 확인",
            "민사집행법 §109① 1주 이내",
            decide,
            legal=True,
        )
    )
    appeal_end = cal.next_biz(decide + timedelta(days=7))
    add(_row("appeal", "즉시항고 기간", "항고가 들어오면 일정이 몇 달 밀릴 수 있어요",
             "민사집행법 §15② 1주", decide + timedelta(days=1), appeal_end, legal=True))  # fmt: skip
    confirm = appeal_end + timedelta(days=1)
    pay_max = cal.prev_biz(add_months(confirm, 1) - timedelta(days=1))
    add(_row("pay_window", "대금지급기한 범위", "법원 통지서의 기한 확인 · 잔금 전 등기부·현장 다시 보기",
             "민사집행규칙 §78 확정 후 1월 안", confirm, pay_max, legal=True))  # fmt: skip
    pay_given = pay_date is not None
    pay = pay_date or cal.next_biz(confirm + timedelta(days=21))
    add(_row("pay", "잔금 납부", "소유권 취득 · 같은 날 인도명령 신청",
             "민사집행법 §135·§136" + ("" if pay_given else " · 날짜는 보통 경우 추정"), pay,
             legal=pay_given, deadline=True))  # fmt: skip
    add(_row("dividend", "배당기일(추정)",
             "배당받는 임차인은 이사·열쇠 확인 뒤 명도확인서 주기" if "tenant_paid" in fl else "배당표 확인",
             "실무 잔금 후 25~40일", pay + timedelta(days=25), pay + timedelta(days=40)))  # fmt: skip
    tax = cal.next_biz(pay + timedelta(days=60))
    add(_row("tax", "취득세 신고·납부 마감", "낙찰가 + 떠안는 보증금으로 신고", "지방세법 §20① 60일",
             tax, legal=True, deadline=True))  # fmt: skip
    add(_row("move_out", "협의로 집이 비는 때", "이사 확인 → 열쇠 받기 → 이사비 지급",
             "실무 잔금 후 2~3개월", pay + timedelta(days=60), pay + timedelta(days=90)))  # fmt: skip
    add(_row("forced", "강제집행까지 가면", "인도명령 → 집행 신청 → 계고 → 본집행",
             "실무 잔금 후 3~4개월", pay + timedelta(days=90), pay + timedelta(days=120)))  # fmt: skip
    if "tenant_unpaid" in fl:
        add(_row("lawsuit", "명도소송이 필요할 수 있어요", "인도명령이 기각되면 판결까지 6개월~1년 반",
                 "실무", pay + timedelta(days=180), pay + timedelta(days=540)))  # fmt: skip
    order_end = cal.next_biz(add_months(pay, 6))
    add(_row("order_deadline", "인도명령 신청 마감", "넘기면 명도소송으로 가야 해요",
             "민사집행법 §136① 대금 낸 뒤 6월", order_end, legal=True, deadline=True))  # fmt: skip

    summary = {
        "pay": pay.isoformat(),
        "move_out": [
            (pay + timedelta(days=60)).isoformat(),
            (pay + timedelta(days=90)).isoformat(),
        ],
        "forced": [(pay + timedelta(days=90)).isoformat(), (pay + timedelta(days=120)).isoformat()],
        "line": f"낙찰되면 잔금 {short(pay)}쯤 · 집이 비는 때 "
        f"{(pay + timedelta(days=60)).month}~{(pay + timedelta(days=90)).month}월",
    }
    status = Status.CONFIRMED if pay_given else Status.ESTIMATED
    return RuleResult(
        {"rows": rows, "summary": summary, "pay_estimated": not pay_given},
        status,
        "schedule.after_sale",
        [{"sale_date": d0.isoformat(), "holidays_n": len(cal.holidays)}],
    )
