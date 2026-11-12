"""REDEV-01: 정비구역 낙찰자의 조합원 자격(도시정비법 §39② · 시행령 §37③5)."""

from typing import Any

from aucs_rules.redev_member import member_transfer
from aucs_rules.risk import signals


def test_rebuild_after_union_is_blocked() -> None:
    v = member_transfer("재건축", "조합설립인가", True).value
    assert v["kind"] == "rebuild" and v["blocked"]


def test_redev_before_disposal_is_open() -> None:
    v = member_transfer("재개발(도시정비형)", "조합설립인가", True).value
    assert v["kind"] == "redev" and not v["blocked"]


def test_redev_after_disposal_is_blocked() -> None:
    assert member_transfer("주택정비형 재개발", "관리처분", True).value["blocked"]


def test_outside_regulated_or_other_law_is_none() -> None:
    assert member_transfer("재건축", "조합설립인가", False).value is None
    assert member_transfer("가로주택정비", "조합설립인가", True).value is None
    assert member_transfer("소규모재건축", "관리처분인가", True).value is None


def test_signal_level_follows_member_rule() -> None:
    z = {"name": "가", "biz_type": "공동주택재건축", "stage": "관리처분"}
    def pick(f: dict[str, Any]) -> Any:
        return next(x for x in signals(f) if x.rule_id == "risk.redev_member")

    s = pick({"in_redev_zone": z, "regulated_area": True})
    assert s.level == "high" and "현금청산" in s.title
    s = pick({"in_redev_zone": z})
    assert s.level == "mid" and "조합원 자격" in s.title
