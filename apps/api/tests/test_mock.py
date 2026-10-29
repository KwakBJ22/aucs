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


def test_group_of():
    from aucs_api.services.mock import group_of

    assert group_of("아파트") == "아파트"
    assert group_of("연립주택,다세대,빌라") == "다세대|연립|빌라"
    assert group_of("대지") is None


def test_interest_shown():
    from aucs_api.services.interest import shown

    assert shown(1, 1) is None
    assert shown(3, 0) == {"viewers_7d": 3, "watchers": 0}
    assert shown(0, 2) == {"viewers_7d": 0, "watchers": 2}


def test_court_bidders_summary():
    from aucs_api.services.court_stats import summarize

    assert summarize([3, 4])["avg"] is None
    s = summarize([1, 2, 3, 4, 10])
    assert s["avg"] == 4.0 and s["median"] == 3 and s["n"] == 5
