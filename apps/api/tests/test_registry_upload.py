from datetime import date

from aucs_api.services.registry import build_ladder, mask_holder, right_from_json, right_to_json
from aucs_rules.rights import Right

D = date


def _rights():
    return [
        Right("갑", "1", "소유권이전", D(2015, 3, 2), holder="홍길동"),
        Right(
            "을",
            "1",
            "근저당권설정",
            D(2019, 5, 10),
            amount_krw=360_000_000,
            holder="주식회사국민은행",
        ),
        Right("갑", "2", "가압류", D(2023, 1, 5), amount_krw=50_000_000),
        Right("갑", "3", "임의경매개시결정", D(2025, 6, 20)),
    ]


def test_mask_holder():
    assert mask_holder("홍길동") == "홍○○"
    assert mask_holder("주식회사국민은행") == "주식회사국민은행"
    assert mask_holder("서울특별시") == "서울특별시"


def test_json_roundtrip_masks():
    j = right_to_json(_rights()[0])
    assert j["holder"] == "홍○○" and j["receipt_date"] == "2015-03-02"
    assert right_from_json(j).receipt_date == D(2015, 3, 2)


def test_ladder_no_hold():
    lad = build_ladder(_rights(), [], D(2025, 9, 1))
    assert lad["base"]["date"] == "2019-05-10"
    assert lad["line"] == "떠안는 돈이 없어요"
    assert next(r for r in lad["rows"] if r["is_base"])["judgment"] == "말소기준"


def test_ladder_senior_tenant_unclaimed():
    ten = [
        {"name": "임차인 김○○", "move_in": "2018-01-02", "deposit_krw": 200_000_000, "claim": None}
    ]
    lad = build_ladder(_rights(), ten, D(2025, 9, 1))
    assert (
        lad["hold_krw"] == 200_000_000 and lad["tenants"][0]["verdict"] == "보증금 전액을 떠안아요"
    )
    claimed = [{**ten[0], "claim": "2025-07-01"}]
    assert build_ladder(_rights(), claimed, D(2025, 9, 1))["line"].startswith("배당에서 못 받는")
