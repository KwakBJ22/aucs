from aucs_rules.fmt import man_text, won, won_small, won_unit


def test_man_text() -> None:
    assert man_text(710_500_000) == "7억 1,050만"
    assert man_text(300_000_000) == "3억"
    assert man_text(16_940_000) == "1,694만"
    assert man_text(0) == "0만"


def test_won_variants() -> None:
    assert won(None) == "-" and won(0) == "-"
    assert won(169_400_000) == "1억 6,940만"
    assert won_small(8_000) == "8,000원" and won_small(0) == "0원"
    assert won_small(12_345_678) == "1,234만"
    assert won_unit(169_400_000) == "1억 6,940만원" and won_unit(300_000_000) == "3억원"
