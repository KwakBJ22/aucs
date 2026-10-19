from aucs_api.services.mock import review


def test_review_bid_sold():
    lines = review(
        {"decision": "bid", "bid_krw": 700_000_000, "max_krw": 720_000_000}, "sold", 710_500_000
    )
    assert lines[0] == "낙찰가 7억 1,050만"
    assert lines[1] == "① 내 금액이 1,050만 모자랐어요"
    assert lines[2].startswith("② 낙찰가가 내 상한(7억 2,000만) 안")


def test_review_skip():
    lines = review({"decision": "skip", "max_krw": 650_000_000}, "sold", 710_500_000)
    assert lines[-1] == "③ 안 들어간 판단: 낙찰가가 상한보다 높아 맞는 판단이었어요"


def test_review_waiting_and_failed():
    assert review({"decision": "bid", "bid_krw": 1}, None, None)[0].startswith("결과가 나오면")
    assert (
        review({"decision": "bid", "bid_krw": 500_000_000}, "failed", None)[1]
        == "내 금액 5억이면 낙찰됐을 거예요"
    )
