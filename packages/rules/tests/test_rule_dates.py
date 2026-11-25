from datetime import date

from aucs_rules.rule_dates import change_line, pay_window, pick, plan

T = date(2026, 11, 25)
ROWS = {
    "acquisition_tax": [(date(2020, 8, 12), {"r": 1}), (date(2027, 1, 1), {"r": 2})],
    "loan_ltv": [(date(2026, 7, 1), {"l": 1})],
}
K = ("acquisition_tax", "loan_ltv")


def test_window_past_sale_uses_today():
    assert pay_window(date(2026, 11, 1), T) == (T, T)
    assert pay_window(None, T) == (T, T)
    assert pay_window(date(2026, 12, 1), T) == (date(2026, 12, 15), date(2027, 1, 15))


def test_before_change_no_notice():
    p = plan(ROWS, K, date(2026, 11, 30), T)
    # 잔금 12/14 ~ 1/14 — 1/1 이 끼어 있음
    assert p["tables"]["acquisition_tax"] == {"r": 1}
    assert p["after"]["tables"]["acquisition_tax"] == {"r": 2}
    assert p["after"]["keys"] == ["acquisition_tax"]
    assert p["applied"] is None


def test_far_before_change_nothing():
    p = plan(ROWS, K, date(2026, 11, 26), T)  # 잔금 12/10 ~ 1/10 → 1/1 낌
    assert p["after"] is not None
    p = plan(ROWS, K, date(2026, 11, 10), T)  # 지난 매각 → 오늘
    assert p["after"] is None and p["applied"] is None


def test_after_change_applied():
    p = plan(ROWS, K, date(2026, 12, 20), T)  # 잔금 1/3 ~ → 새 세율
    assert p["tables"]["acquisition_tax"] == {"r": 2}
    assert p["applied"]["keys"] == ["acquisition_tax"] and p["after"] is None
    assert p["used"]["acquisition_tax"] == "2027-01-01"


def test_missing_table():
    assert pick({"loan_ltv": []}, ("loan_ltv",), T) is None


def test_line_only_when_amount_changes():
    assert change_line(["acquisition_tax"], date(2027, 1, 1), 100_000_000, 100_005_000, applied=False) is None
    s = change_line(["acquisition_tax"], date(2027, 1, 1), 100_000_000, 103_000_000, applied=False)
    assert s == "1월 1일부터 취득세 기준이 바뀌어요 · 잔금을 그날부터 내면 300만 원 더 들어요"


def test_basic_rate_from_table():
    from aucs_rules.calc import acquisition_tax

    t = {"basic": [[600_000_000, 2.0], [None, 3.0]], "heavy": {"other": {}}, "edu_rate_of_basic": 10,
         "edu_heavy": 0.4, "farm_over85": {"basic": 0.2}}
    v = acquisition_tax(400_000_000, homes_after=1, cls="metro", area_m2=59, table=t).value
    assert v["rate"] == 2.0
    t["basic"] = [[600_000_000, 1.0], [900_000_000, "formula"], [None, 3.0]]
    assert acquisition_tax(750_000_000, homes_after=1, cls="metro", area_m2=59, table=t).value["rate"] == 2.0
