from datetime import date, timedelta

from aucs_rules.costs import bid_cap, commercial_over_limit, real_cost
from aucs_rules.risk import signals
from aucs_rules.sale_rate import (
    Sale,
    court_cell,
    effective_failed,
    local_peers,
    new_item,
    rate_range,
    restarted,
)

D = date(2026, 10, 15)
TBL = {"seoul": {"limit_krw": 900_000_000}, "overcrowded": {"limit_krw": 690_000_000, "also": ["부산"]},
       "metro": {"limit_krw": 540_000_000, "also": ["세종", "용인"]}, "other": {"limit_krw": 370_000_000},
       "rent_multiplier": 100}  # fmt: skip


def _s(rate: float, court: str = "B1", sg: str = "수지구", mr: float = 70, days: int = 10) -> Sale:
    return Sale(D - timedelta(days=days), "경기", sg, "아파트", 84, 1, rate, False, court, mr)


def test_trim_drops_outliers() -> None:
    sales = [_s(80)] * 12 + [_s(664), _s(50)]
    v = rate_range(
        sales,
        as_of=D,
        sido="경기",
        sigungu="수지구",
        usage_name="아파트",
        area_m2=84,
        failed_count=1,
    ).value
    assert v["n"] == 12 and v["p75"] == 80


def test_court_cell_shifts_base_when_big_and_far() -> None:
    sales = [_s(90)] * 30 + [_s(80, court="B2")] * 5
    v = court_cell(
        sales, as_of=D, court_code="B1", usage_name="아파트", min_rate=70, base_p50=83
    ).value
    assert v["n"] == 30 and v["use_as_base"] is True and v["diff"] == 7
    few = court_cell(
        sales[:10], as_of=D, court_code="B1", usage_name="아파트", min_rate=70, base_p50=83
    ).value
    assert few["use_as_base"] is False


def test_local_peers_warns() -> None:
    v = local_peers([_s(95), _s(100), _s(108)], as_of=D, sigungu="수지구", usage_name="아파트",
                    min_rate=70, review_p50=83.5).value  # fmt: skip
    assert v["warn"] is True and v["lo"] == 95


def test_new_item() -> None:
    assert new_item(0, 500, 600).value is True
    assert new_item(0, 480, 600).value is False
    assert new_item(1, 500, 600).value is False


def test_low_appraisal_needs_year_old() -> None:
    f = {"appraisal_krw": 90, "market_price_krw": 100, "as_of": D}
    young = signals({**f, "appraisal_date": D - timedelta(days=100)})
    old = signals({**f, "appraisal_date": D - timedelta(days=400)})
    assert not any(s.rule_id == "risk.low_appraisal" for s in young)
    assert any(s.rule_id == "risk.low_appraisal" for s in old)


def test_signal_has_failure_type() -> None:
    s = signals({"senior_tenant_assumed": True})[0]
    assert s.ftype == "T1"


def test_costs() -> None:
    r = real_cost(300_000_000, assumed_krw=80_000_000, tax_krw=3_300_000).value
    assert r["total_krw"] == 383_300_000 and r["full_cash_krw"] == 383_300_000
    c = bid_cap(53_000_000, assumed_krw=87_000_000, min_price_krw=10_000_000).value
    assert c["no_gain"] is True


def test_commercial_limit_region() -> None:
    v = commercial_over_limit(500_000_000, 1_000_000, sido="경기", sigungu="용인시",
                              region_class="overcrowded", table=TBL).value  # fmt: skip
    assert v["region"] == "metro" and v["converted_krw"] == 600_000_000 and v["over"] is True


def test_effective_failed_restart() -> None:
    # 2024타경57221: 유찰 12회 뒤 대항력 포기로 최저가=감정가 3.79억
    assert effective_failed(12, 379_000_000, 379_000_000) == 0
    assert restarted(12, 379_000_000, 379_000_000) is True
    assert effective_failed(2, 100, 64) == 2
    assert restarted(0, 100, 100) is False


def test_heavy_failed_not_mixed_with_light_and_capped_by_last_fail():
    """11/8 수원 2024타경101239: 9번 유찰 오피스텔(최저가 468만, 감정가 1.16억)을
    1~2번 유찰 물건과 견줘 「보통 7,273만」으로 냈음 → 유찰 많은 것끼리 + 지난 유찰가(669만) 위로 안 감."""
    from datetime import date as _d

    from aucs_rules.sale_rate import Sale, adjusted_rates, fail_group, last_failed_price

    day = _d(2026, 10, 1)
    light = [Sale(day, "경기도", "수원시", "오피스텔", 30.0, 1, 60.0 + i, False) for i in range(20)]
    heavy = [Sale(day, "경기도", "수원시", "오피스텔", 30.0, 8, 5.0 + i, False) for i in range(3)]
    r = rate_range(light + heavy, as_of=_d(2026, 11, 8), sido="경기도", sigungu="수원시",
                   usage_name="오피스텔", area_m2=30.0, failed_count=9)  # fmt: skip
    assert r.value is not None and r.value["p50"] < 10  # 1회 유찰 물건(60%대)이 섞이지 않음
    assert fail_group(9) == fail_group(5) == 5 and fail_group(2) == 2
    app, mn = 116_000_000, 4_681_000
    assert last_failed_price(app, mn, 30) == 6_687_143
    a = adjusted_rates({"p25": 50.5, "p50": 62.7, "p75": 68.3}, None, app, mn, 30)
    assert a is not None and a["capped"]
    assert mn <= app * a["mid"] / 100 <= 6_687_143 and app * a["hi"] / 100 <= 6_687_143 + 1
    assert adjusted_rates({"p25": 50, "p50": 60, "p75": 70}, None, 100, 100)["capped"] is False
