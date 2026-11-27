"""감정평가서 받은 폴더(11/28) — 같은 사건번호가 두 법원에 있을 때 글 속 법원 이름으로 고르기."""

from aucs_workers.collectors.appraisal_folder import pick_court


def test_pick_court_by_name() -> None:
    two = ["B000240-2025타경1502", "B000250-2025타경1502"]
    text = "제 출 처 수원지방법원 사법보좌관 … 법원경매 수원지방법원 경매5계"
    assert pick_court(two, text) == ["B000250-2025타경1502"]
    seoul = ["B000211-2025타경51389", "B000215-2025타경51389"]
    assert pick_court(seoul, "서울 서부 지방법원 귀중") == ["B000215-2025타경51389"]


def test_pick_court_branch_first_and_unknown_kept() -> None:
    two = ["B000250-2025타경9", "B000253-2025타경9"]
    assert pick_court(two, "수원지방법원 평택지원 경매3계") == ["B000253-2025타경9"]
    assert pick_court(two, "글 없음") == two
