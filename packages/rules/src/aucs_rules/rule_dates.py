"""기준표(ref.rule_tables)를 「잔금 내는 날」로 고르기 (11/25 대표님 — 세법이 바뀌면 낙찰받는 손님이 영향을 받음).

취득세는 대금을 다 낸 날(경매 취득일), 대출 비율 · 규제지역은 대출을 받는 날 — 둘 다 잔금일이라
오늘 기준이 아니라 잔금을 낼 수 있는 기간으로 줄을 고릅니다.

잔금 기간(법원 경매):
  매각기일 + 7일 매각결정기일(민사집행법 §109) + 7일 즉시항고 기간 = 매각허가결정 확정 → 가장 이른 잔금일
  확정일부터 1월 안의 날로 대금지급기한(민사집행규칙 §78) → 가장 늦은 잔금일
  항고가 걸리면 더 늦어질 수 있음(그때는 화면 문구로만 알림). 공매도 같은 기간으로 셈(공매 기간은 확인 안 함).

조건(줄의 시행일 valid_from 이 어디에 있나):
  · 가장 이른 잔금일 이전(오늘 이전 포함) → 그 줄로 셈. 시행일이 오늘 뒤면 「바뀐 기준으로 셈」 알림.
  · 잔금 기간 안 → 이른 날 기준으로 셈 + 늦은 날 기준도 셈해 차이를 알림(손님이 잔금일을 고를 수 있음).
  · 가장 늦은 잔금일 뒤 → 쓰지 않음.
  알림은 이 물건의 금액이 실제로 달라질 때만(셈은 부르는 쪽이 두 번 해서 견줌).
기준표에는 확정된 것(공포 · 고시된 것)만 넣습니다 — 개정 추진 중인 안은 넣지 않음.
"""

from datetime import date, timedelta
from typing import Any

PAY_EARLY_DAYS = 14  # 매각결정 7일 + 항고 7일
PAY_LATE_DAYS = 45  # 확정 + 1월(통지까지 며칠 더)

Rows = dict[str, list[tuple[date, Any]]]  # rule_key → [(valid_from, value)]


def pay_window(sale_date: date | None, today: date) -> tuple[date, date]:
    """잔금을 낼 수 있는 기간. 매각기일이 없거나 지났으면 오늘(이미 낙찰된 것은 굳힌 값을 씀)."""
    if not sale_date or sale_date < today:
        return today, today
    return sale_date + timedelta(days=PAY_EARLY_DAYS), sale_date + timedelta(days=PAY_LATE_DAYS)


def pick(rows: Rows, keys: tuple[str, ...] | list[str], day: date) -> dict[str, Any] | None:
    """day 에 시행 중인 줄(시행일이 가장 늦은 것). 하나라도 없으면 None."""
    out: dict[str, Any] = {}
    for k in keys:
        cands = [(vf, v) for vf, v in rows.get(k, []) if vf <= day]
        if not cands:
            return None
        out[k] = max(cands, key=lambda x: x[0])[1]
    return out


def used(rows: Rows, keys: tuple[str, ...] | list[str], day: date) -> dict[str, str]:
    """고른 줄의 시행일(다시 분석할 물건을 고를 때 견줌)."""
    out: dict[str, str] = {}
    for k in keys:
        vfs = [vf for vf, _ in rows.get(k, []) if vf <= day]
        out[k] = max(vfs).isoformat() if vfs else ""
    return out


def plan(rows: Rows, keys: tuple[str, ...] | list[str], sale_date: date | None, today: date) -> dict[str, Any]:
    """이 물건에 쓸 기준표와, 바뀌는 날이 끼면 그 내용.

    {"day": 셈한 날, "tables": …, "after": {"day", "tables", "keys", "from"} | None,
     "applied": {"keys", "from"} | None, "used": {key: valid_from}}
    """
    early, late = pay_window(sale_date, today)
    tables = pick(rows, keys, early)
    out: dict[str, Any] = {"day": early, "tables": tables, "after": None, "applied": None,
                           "used": used(rows, keys, early)}  # fmt: skip
    # 오늘은 아직 아닌데 이른 잔금일엔 시행 중인 줄 → 바뀐 기준으로 셈했다고 알림
    ahead = sorted({vf for k in keys for vf, _ in rows.get(k, []) if today < vf <= early})
    if ahead:
        out["applied"] = {"from": ahead[-1],
                          "keys": [k for k in keys if any(today < vf <= early for vf, _ in rows.get(k, []))]}  # fmt: skip
    # 잔금 기간 안에 바뀌는 줄 → 늦은 날 기준도
    inside = sorted({vf for k in keys for vf, _ in rows.get(k, []) if early < vf <= late})
    if inside:
        day = inside[0]
        out["after"] = {"day": day, "from": day, "tables": pick(rows, keys, day),
                        "keys": [k for k in keys if any(vf == day for vf, _ in rows.get(k, []))]}  # fmt: skip
    return out


def today_tables(rows: Rows, keys: tuple[str, ...] | list[str], today: date) -> dict[str, Any] | None:
    return pick(rows, keys, today)


KEY_NAME = {
    "acquisition_tax": "취득세", "first_home_relief": "생애최초 감면", "loan_ltv": "대출 비율",
    "regulated_areas": "규제지역", "dsr": "DSR",
}  # fmt: skip


def change_line(keys: list[str], since: date, before_krw: int, after_krw: int, *, applied: bool) -> str | None:
    """화면 한 줄. 금액이 1만 원 넘게 달라질 때만."""
    diff = after_krw - before_krw
    if abs(diff) < 10_000:
        return None
    what = " · ".join(dict.fromkeys(KEY_NAME.get(k, k) for k in keys))
    md = f"{since.month}월 {since.day}일"
    amt = f"{abs(diff) // 10_000:,}만 원 {'더' if diff > 0 else '덜'}"
    if applied:
        return f"{md}부터 {what} 기준이 바뀌어 바뀐 기준으로 셈했어요 · 지금 기준보다 {amt} 들어요"
    return f"{md}부터 {what} 기준이 바뀌어요 · 잔금을 그날부터 내면 {amt} 들어요"
