from datetime import date

from aucs_rules.distribution import Claim, distribute
from aucs_rules.fix_dictionary import normalize_purpose
from aucs_rules.price import Trade, market_price
from aucs_rules.result import Status
from aucs_rules.risk import signals, top_signal
from aucs_rules.sale_rate import Sale, next_round_min_price, rate_range
from aucs_rules.tenants import Tenant, opposing_power, priority_date, small_lease_amount

D = date


def test_fix_dictionary() -> None:
    assert normalize_purpose("가암큐") == "가압류"
    assert normalize_purpose("근저당권설정") == "근저당권설정"
    assert normalize_purpose("알수없음") is None


def test_opposing_power_same_day_is_none() -> None:
    assert opposing_power(Tenant(D(2021, 3, 31)), D(2021, 3, 31)).value is False
    assert opposing_power(Tenant(D(2021, 3, 30)), D(2021, 3, 31)).value is True
    assert opposing_power(Tenant(None), D(2021, 3, 31)).status == Status.UNKNOWN


def test_priority_date_is_later_of_two() -> None:
    assert priority_date(Tenant(D(2022, 1, 1), fixed_date=D(2021, 12, 1))).value == D(2022, 1, 2)


def test_small_lease_uses_first_security_date() -> None:
    table = [
        {"valid_from": D(2021, 5, 11), "valid_to": D(2023, 2, 20), "region_class": "seoul",
         "deposit_limit_krw": 150_000_000, "amount_krw": 50_000_000},
        {"valid_from": D(2023, 2, 21), "valid_to": None, "region_class": "seoul",
         "deposit_limit_krw": 165_000_000, "amount_krw": 55_000_000},
    ]  # fmt: skip
    t = Tenant(D(2023, 3, 1), deposit_krw=160_000_000)
    assert small_lease_amount(t, "seoul", D(2022, 1, 1), None, 600_000_000, table).value == 0
    assert (
        small_lease_amount(t, "seoul", D(2023, 3, 1), None, 600_000_000, table).value == 55_000_000
    )
    assert (
        small_lease_amount(t, "seoul", D(2023, 3, 1), None, 80_000_000, table).value == 40_000_000
    )


def test_distribution_order() -> None:
    claims = [
        Claim("비용", "cost", 5_000_000),
        Claim("소액", "top_priority", 50_000_000),
        Claim("근저당", "dated", 300_000_000, D(2021, 3, 31)),
        Claim("임차인", "dated", 200_000_000, D(2022, 1, 1)),
        Claim("가압류A", "general", 60_000_000),
        Claim("가압류B", "general", 40_000_000),
    ]
    r = distribute(500_000_000, claims)
    paid = r.value["paid"]
    assert paid["비용"] == 5_000_000 and paid["소액"] == 50_000_000
    assert paid["근저당"] == 300_000_000 and paid["임차인"] == 145_000_000
    assert paid.get("가압류A", 0) == 0
    assert distribute(1_000_000, [Claim("x", "dated", None)]).status == Status.NEEDS_CHECK


def test_sale_rate_falls_back_to_sido() -> None:
    sales = [Sale(D(2026, 9, 1), "경기도", "용인시", "아파트", 84.0, 1, 80 + i) for i in range(12)]
    sales += [Sale(D(2026, 9, 1), "경기도", "용인시", "아파트", 84.0, 1, 10, is_special_case=True)]
    r = rate_range(sales, as_of=D(2026, 10, 17), sido="경기도", sigungu="수원시",
                   usage_name="아파트", area_m2=84.9, failed_count=1)  # fmt: skip
    assert r.value["scope"] == "sido" and r.value["n"] == 12 and r.value["p50"] == 85.5
    assert next_round_min_price(100, None).status == Status.UNKNOWN
    assert next_round_min_price(710_500_000, 30).value == 497_350_000


def test_market_price_levels() -> None:
    trades = [
        Trade(D(2026, m, 1), 900_000_000 + m, 167.5, 5, "성복힐스테이트3차") for m in (3, 5, 7)
    ]
    r = market_price(
        trades, as_of=D(2026, 10, 17), complex_name="성복힐스테이트3차", area_m2=167.576
    )
    assert r.value["level"] == 1 and r.value["n"] == 3
    assert (
        market_price([], as_of=D(2026, 10, 17), complex_name=None, area_m2=84).status
        == Status.UNKNOWN
    )


def test_risk_fatal_first_and_villa() -> None:
    sig = signals(
        {"is_share": True, "family_tenant": True, "usage_code": "21101", "usage_text": "다세대주택"}
    )
    assert top_signal(sig).level == "fatal"
    assert any(s.rule_id == "risk.neighborhood_villa" for s in sig)
    assert signals({"tenants_checked": False})[0].status == Status.UNKNOWN


def test_small_lease_from_rule_table_rows() -> None:
    from aucs_rules.tenants import flatten_small_lease_table

    rows = [{"valid_from": D(2023, 2, 21), "valid_to": None,
             "value": {"seoul": {"deposit_limit_krw": 165_000_000, "amount_krw": 55_000_000}}}]  # fmt: skip
    t = Tenant(D(2024, 1, 1), deposit_krw=100_000_000)
    assert (
        small_lease_amount(
            t, "seoul", D(2024, 1, 1), None, None, flatten_small_lease_table(rows)
        ).value
        == 55_000_000
    )
