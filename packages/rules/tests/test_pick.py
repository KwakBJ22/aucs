"""추천 점수(PICK-01) — 걸러내기·목적별 비중·이유 한 줄."""

from aucs_rules.pick import PickInput, diversify, pick_score


def _x(**kw: object) -> PickInput:
    base: dict[str, object] = dict(
        usage="아파트", appraisal_krw=500_000_000, min_price_krw=350_000_000, failed_count=1,
        area_m2=84.0, is_share=False, is_special=False, d_day=20,
        analysis={"market": {"price_krw": 520_000_000}, "sale_rate": {"p50": 80},
                  "court_cell": {"p50": 85}, "signals": [], "tenant_count": 0},
    )  # fmt: skip
    base.update(kw)
    return PickInput(**base)  # type: ignore[arg-type]


def test_cheap_safe_apartment_scores_high_with_reasons() -> None:
    v = pick_score(_x(), "live").value
    assert v["excluded"] is None
    assert v["score"] >= 70
    assert v["reasons"][0].startswith("시세보다 1억 2천만 원")  # 예상 낙찰가 4억 vs 시세 5.2억
    assert "위험 신호 없음" in v["reasons"]


def test_guest_has_no_purpose_part() -> None:
    v = pick_score(_x(), None).value
    assert "fit" not in v["parts"] and "yield" not in v["parts"]


def test_purpose_changes_order() -> None:
    officetel = _x(
        usage="오피스텔", area_m2=25.0, rent={"monthly_krw": 2_000_000, "deposit_krw": 10_000_000}
    )
    apt = _x()
    assert pick_score(officetel, "rent").value["score"] > pick_score(apt, "rent").value["score"]
    assert pick_score(apt, "live").value["score"] > pick_score(officetel, "live").value["score"]
    assert pick_score(officetel, "rent").value["reasons"][0].startswith("월세 수익률")


def test_fatal_signal_is_excluded() -> None:
    v = pick_score(_x(analysis={"signals": [{"level": "fatal", "status": "추정"}]})).value
    assert v["excluded"] == "치명 신호" and v["score"] == 0


def test_share_only_for_invest() -> None:
    assert pick_score(_x(is_share=True)).value["excluded"] == "지분·특수매각"
    assert pick_score(_x(is_share=True), "resell").value["excluded"] is None


def test_diversify() -> None:
    rows = [{"place": "강남구", "building": "A"}, {"place": "강남구", "building": "A"},
            {"place": "강남구", "building": "B"}, {"place": "강남구", "building": "C"},
            {"place": "서초구", "building": "D"}]  # fmt: skip
    assert [r["building"] for r in diversify(rows, 5)] == ["A", "B", "D"]


def test_overvalued_without_market_not_picked() -> None:
    """11/9 수원 2024타경101239: 시세 없이 9번 유찰(감정가의 4%) — 「아주 싸다」가 아니라 감정가가 부풀려진 것."""
    no_mkt = {"sale_rate": {"p50": 60}, "signals": [], "tenant_count": 0}
    heavy = _x(usage="오피스텔", appraisal_krw=116_000_000, min_price_krw=4_681_000,
               failed_count=9, analysis=no_mkt)  # fmt: skip
    assert pick_score(heavy).value["excluded"] == "시세 없이 많이 유찰"
    low = _x(min_price_krw=120_000_000, failed_count=3, analysis=no_mkt)  # 감정가의 24%
    assert pick_score(low).value["excluded"] == "시세 없이 많이 유찰"
    one = pick_score(_x(failed_count=1, analysis=no_mkt)).value
    three = pick_score(_x(failed_count=3, min_price_krw=256_000_000, analysis=no_mkt)).value
    assert one["excluded"] is None and three["excluded"] is None
    assert three["parts"]["value"] < one["parts"]["value"]  # 유찰이 많으면 「싸다」 점수를 깎음
    # 시세가 있으면 그대로 견줌
    assert pick_score(_x(failed_count=9, min_price_krw=50_000_000)).value["excluded"] is None


def test_assumed_debt_not_picked_and_unknown_not_safe() -> None:
    """11/9 강남 논현동: 선순위 임차권 인수 물건이 「시세보다 2억 싸게」로 추천 1위였음."""
    t1 = {"ftype": "T1", "level": "high", "status": "추정", "title": "선순위 임차권 인수"}
    a = {"market": {"price_krw": 520_000_000}, "sale_rate": {"p50": 80}, "signals": [t1]}
    assert pick_score(_x(analysis=a)).value["excluded"] == "떠안는 돈 있음"
    unk = {"level": "info", "status": "모름", "title": "임차인 자료 미확인"}
    b = {"market": {"price_krw": 520_000_000}, "sale_rate": {"p50": 80}, "signals": [unk]}
    assert "위험 신호 없음" not in pick_score(_x(analysis=b)).value["reasons"]


def test_diversify_one_per_case() -> None:
    rows = [
        {"item_id": f"B1-2025타경1839-{n}", "court": "수원", "case_no": "2025타경1839",
         "place": f"구{n}", "building": None}
        for n in (1, 2)
    ] + [{"item_id": "B1-2025타경1-1", "court": "수원", "case_no": "2025타경1", "place": "구9",
          "building": None}]  # fmt: skip
    got = diversify(rows, 5)
    assert [r["item_id"] for r in got] == ["B1-2025타경1839-1", "B1-2025타경1-1"]
    assert diversify(rows, 5, skip_cases={"수원|2025타경1839"})[0]["item_id"] == "B1-2025타경1-1"
