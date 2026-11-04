"""추천 점수(PICK-01) — 걸러내기·싸게 살 여지·이유 한 줄."""

from aucs_rules.pick import PickInput, diversify, pick_score, timing_by_days


def _x(**kw: object) -> PickInput:
    base: dict[str, object] = dict(
        usage="아파트", appraisal_krw=500_000_000, min_price_krw=350_000_000, failed_count=1,
        area_m2=84.0, is_share=False, is_special=False,
        analysis={"market": {"price_krw": 520_000_000}, "sale_rate": {"p50": 80},
                  "court_cell": {"p50": 85}, "signals": [], "tenant_count": 0},
    )  # fmt: skip
    base.update(kw)
    return PickInput(**base)  # type: ignore[arg-type]


def test_cheap_safe_apartment_scores_high_with_reasons() -> None:
    v = pick_score(_x()).value
    assert v["excluded"] is None
    assert v["score"] >= 70
    assert v["reasons"][0].startswith("시세보다 1억 2천만 원")  # 예상 낙찰가 4억 vs 시세 5.2억
    assert "위험 신호 없음" in v["reasons"]


def test_fatal_signal_is_excluded() -> None:
    v = pick_score(_x(analysis={"signals": [{"level": "fatal", "status": "추정"}]})).value
    assert v["excluded"] == "치명 신호" and v["score"] == 0


def test_share_only_for_invest() -> None:
    assert pick_score(_x(is_share=True)).value["excluded"] == "지분·특수매각"
    assert pick_score(_x(is_share=True), "invest").value["excluded"] is None


def test_timing_and_diversify() -> None:
    assert timing_by_days(20) == 4 and timing_by_days(5) == 0
    rows = [{"place": "강남구", "building": "A"}, {"place": "강남구", "building": "A"},
            {"place": "강남구", "building": "B"}, {"place": "강남구", "building": "C"},
            {"place": "서초구", "building": "D"}]  # fmt: skip
    got = diversify(rows, 5)
    assert [r["building"] for r in got] == ["A", "B", "D"]
