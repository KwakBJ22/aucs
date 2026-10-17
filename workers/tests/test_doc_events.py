import json
from datetime import date
from pathlib import Path

from aucs_rules.progress import judge_progress
from aucs_workers.extract.doc_events import classify, importance

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "doc_events_sample.json").read_text(encoding="utf-8")
)


def test_same_as_local_system() -> None:
    """지금 시스템 SQL 분류와 같은 결과 (분류마다 최대 8건, 실제 문건)."""
    wrong = [(r["text"], r["expect"], classify(r["text"], r["kind"])) for r in SAMPLE]
    wrong = [w for w in wrong if w[1] != w[2]]
    assert not wrong, wrong[:5]


def test_late_claim_is_high() -> None:
    assert importance("권리신고·배당요구", date(2025, 8, 1), date(2025, 7, 1)) == ("high", True)
    assert importance("권리신고·배당요구", date(2025, 6, 1), date(2025, 7, 1)) == ("mid", False)
    assert importance("서류 보정", None, None) == ("low", False)


def test_progress() -> None:
    assert judge_progress([(date(2025, 5, 1), "정지·취하 시도")]).value == "기일이 바뀔 수 있음"
    ev = [(date(2025, 5, 1), "회생·파산"), (date(2025, 6, 1), "경매 속행 신청")]
    assert judge_progress(ev).value == "속행 신청됨"


def test_mask_keeps_document_words() -> None:
    from aucs_workers.extract.mask import mask_names

    assert mask_names("임차인 홍길동 배당요구") == "임차인 홍○○ 배당요구"
    assert mask_names("임차인통지서 발송") == "임차인통지서 발송"
    assert mask_names("채권자 변경신청서 제출") == "채권자 변경신청서 제출"
    assert mask_names("채무자 겸소유자 김철수") == "채무자 겸소유자 김○○"
