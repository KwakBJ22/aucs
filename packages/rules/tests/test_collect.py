"""모아 보기(COLLECT-01) — 어느 모음에 드는지와 이유 한 줄."""

from aucs_rules.collect import CollectInput, collect


def _x(**kw: object) -> CollectInput:
    base: dict[str, object] = dict(
        appraisal_krw=500_000_000, min_price_krw=350_000_000, is_share=False, is_special=False,
        analysis={"market": {"price_krw": 600_000_000}, "sale_rate": {"p50": 80},
                  "signals": [], "tenant_count": 0},
    )  # fmt: skip
    base.update(kw)
    return CollectInput(**base)  # type: ignore[arg-type]


def test_cheap_rising_safe() -> None:
    v = collect(_x()).value
    assert v["cheap"]["reason"] == "시세보다 2억 원(33%) 낮게 살 여지"  # 예상 4억 vs 시세 6억
    assert v["rising"]["reason"] == "감정가보다 지금 시세가 20% 높아요"
    assert v["safe"]["reason"] == "위험 신호 없음 · 임차인 없음"
    assert "special" not in v and "station" not in v


def test_unknown_signal_is_not_safe() -> None:
    a = {"signals": [{"level": "info", "status": "모름", "title": "임차인 자료 미확인"}]}
    assert "safe" not in collect(_x(analysis=a)).value


def test_fatal_goes_only_to_special() -> None:
    a = {"market": {"price_krw": 900_000_000}, "sale_rate": {"p50": 80},
         "signals": [{"level": "fatal", "status": "확정", "title": "선순위 전세권 인수"}]}  # fmt: skip
    v = collect(_x(analysis=a, station=("공덕", 300))).value
    assert set(v) == {"special"}
    assert v["special"]["reason"] == "선순위 전세권 인수"


def test_station_name_and_limit() -> None:
    assert collect(_x(station=("공덕", 320))).value["station"]["reason"] == "공덕역 320m"
    assert collect(_x(station=("서울역", 100))).value["station"]["reason"] == "서울역 100m"
    assert "station" not in collect(_x(station=("공덕", 700))).value


def test_no_price_no_collection() -> None:
    assert collect(_x(min_price_krw=None)).value == {}
