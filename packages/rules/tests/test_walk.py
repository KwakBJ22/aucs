from aucs_rules.walk import walk_estimate


def test_walk_estimate() -> None:
    assert walk_estimate(420).value == {"walk_m": 550, "walk_min": 9}
    assert walk_estimate(0).value == {"walk_m": 0, "walk_min": 1}
    assert walk_estimate(None).value is None
