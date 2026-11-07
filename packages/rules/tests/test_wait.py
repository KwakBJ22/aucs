"""기다리면 더 싸질까(WAIT-01) — 실제 유찰 비율·표본 모자랄 때."""

from aucs_rules.wait import fail_odds, round_bucket


def test_court_level_likely() -> None:
    stats = {("B000250", "apt", 0): (45, 50)}
    v = fail_odds(stats, "B000250", "apt", 0).value
    assert v == {"fail": 45, "n": 50, "pct": 90, "of10": 9, "likely": True, "scope": "court"}


def test_small_court_falls_back_to_all_courts() -> None:
    stats = {("B000250", "apt", 1): (5, 10), ("B000210", "apt", 1): (20, 40)}
    v = fail_odds(stats, "B000250", "apt", 1).value
    assert v["scope"] == "all" and v["n"] == 50 and v["pct"] == 50 and v["likely"] is False


def test_too_few_is_unknown() -> None:
    assert fail_odds({("B000250", "apt", 2): (3, 5)}, "B000250", "apt", 2).value is None


def test_round_bucket() -> None:
    assert [round_bucket(x) for x in (None, 0, 2, 7)] == [0, 0, 2, 3]
