"""환불 규칙(11/3): 7일 안 미사용 전액 · 매달 7일 안은 쓴 날만 · 1년 중간 해지는 매달 요금으로 계산(위약금 없음) · 한 건은 열기 전 전액."""

from datetime import date, timedelta

from aucs_api.services.billing import refund_estimate

D = date(2026, 11, 1)
YEAR_END = D + timedelta(days=364)


def on(day: int) -> date:
    return D + timedelta(days=day - 1)  # day 번째 날(결제일 = 1일째)


def test_seven_days_unopened_full() -> None:
    for period in ("month", "year", "one"):
        assert (
            refund_estimate(period, 29_000, D, on(7), YEAR_END, opened=False).amount_krw == 29_000
        )


def test_month_within_seven_days_used_days_only() -> None:
    assert refund_estimate(
        "month", 29_000, D, on(3), on(30), opened=True
    ).amount_krw == 29_000 - round(29_000 * 3 / 30)


def test_month_after_seven_days_no_refund() -> None:
    assert refund_estimate("month", 29_000, D, on(8), on(30), opened=True).amount_krw == 0


def test_year_counts_used_days_at_monthly_price() -> None:
    # 6개월(180일) 쓰면 매달권 6개월(174,000원)을 낸 것과 같게 → 116,000원 돌려줌
    r = refund_estimate("year", 290_000, D, on(180), YEAR_END, opened=True, monthly=29_000)
    assert r.amount_krw == 116_000


def test_year_after_ten_months_nothing_left() -> None:
    assert (
        refund_estimate(
            "year", 290_000, D, on(330), YEAR_END, opened=True, monthly=29_000
        ).amount_krw
        == 0
    )


def test_one_opened_no_refund() -> None:
    assert refund_estimate("one", 9_900, D, D, D + timedelta(days=10), opened=True).amount_krw == 0
