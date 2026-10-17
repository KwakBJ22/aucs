from datetime import date

from aucs_workers.collectors.trades import months_back, parse_trade

REGION = {("41465", "성복동"): "4146510600"}


def test_parse_sale_and_cancelled() -> None:
    it = {"dealYear": "2026", "dealMonth": "9", "dealDay": "3", "umdNm": "성복동", "aptNm": "성복힐스테이트3차",
          "jibun": "760", "excluUseAr": "167.576", "floor": "5", "buildYear": "2004", "dealAmount": "95,000"}  # fmt: skip
    t = parse_trade(it, "sale", "apt", "41465", REGION)
    assert (
        t
        and t["price_krw"] == 950_000_000
        and t["region_code"] == "4146510600"
        and t["deal_date"] == date(2026, 9, 3)
    )
    assert parse_trade({**it, "cdealType": "O"}, "sale", "apt", "41465", REGION) is None


def test_parse_lease() -> None:
    it = {"dealYear": "2026", "dealMonth": "8", "dealDay": "1", "umdNm": "역삼동", "deposit": "50,000", "monthlyRent": "120",
          "preDeposit": "45,000", "contractType": "갱신", "excluUseAr": "84.9"}  # fmt: skip
    t = parse_trade(it, "lease", "apt", "11680", {})
    assert (
        t
        and t["deposit_krw"] == 500_000_000
        and t["monthly_rent_krw"] == 1_200_000
        and t["price_krw"] is None
    )
    assert t["prev_deposit_krw"] == 450_000_000 and t["region_code"] is None


def test_months_back() -> None:
    assert months_back(3, date(2026, 1, 15)) == ["202601", "202512", "202511"]


def test_eup_ri_falls_back_to_eup() -> None:
    it = {
        "dealYear": "2026",
        "dealMonth": "10",
        "dealDay": "1",
        "umdNm": "진접읍 금곡리",
        "dealAmount": "30,000",
    }
    t = parse_trade(it, "sale", "apt", "41360", {("41360", "진접읍"): "4136025000"})
    assert t and t["region_code"] == "4136025000"
