"""포인트 벌기 — 돈이 걸린 판단만."""

from aucs_rules.points import points_for

T = {
    "registry": 1000,
    "appraisal": 500,
    "daily_max": {"registry": 5, "appraisal": 5},
    "registry_fresh_days": 30,
}


def _p(kind: str, **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "matched": True,
        "today_count": 0,
        "paid_before": False,
        "days_since_last_paid": None,
    }
    base.update(kw)
    return points_for(kind, T, **base).value  # type: ignore[arg-type]


def test_points_rules() -> None:
    assert _p("registry") == {"points": 1000, "why": "first"}
    assert _p("appraisal") == {"points": 500, "why": "first"}
    assert _p("registry", matched=False)["points"] == 0
    assert _p("registry", today_count=5) == {"points": 0, "why": "limit"}
    assert _p("appraisal", paid_before=True, days_since_last_paid=400)["why"] == "already"
    assert _p("registry", paid_before=True, days_since_last_paid=10)["why"] == "already"
    assert _p("registry", paid_before=True, days_since_last_paid=31) == {
        "points": 1000,
        "why": "fresh",
    }
