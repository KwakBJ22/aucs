"""예정물건(배당요구종기공고) 한 줄 읽기 — 11/27 법원 화면에서 본 칸 모양(이름 칸은 뺌)."""

from datetime import date

from aucs_workers.collectors.court_notices import dept_codes, parse_notice

ROW = {
    "userCsNo": "2026타경101761", "csNo": "20260130101761", "cortOfcCd": "B000210", "jdbnCd": "1001",
    "csCmdcYmd": "20260915", "dstrtDemnLstprdYmd": "20261127", "dstrtDemnLstprdPbancYmd": "20260918",
    "adongSdNm": "서울특별시", "adongSggNm": "관악구", "adongEmdNm": "신림동", "adongRiNm": "",
    "rprsLtnoAddr": "1421-1", "RDNM": "", "rdnmBldNo": "42", "rdnmRefcAddr": "(신림동,신림큐브)",
    "bldNm": "신림큐브", "bldDtlDts": " 8층809호", "mgakMokmulCnt": "",
    "realOwnr": "홍길동", "rprsDebtrNm": "홍길동",
}  # fmt: skip


def test_parse_notice() -> None:
    r = parse_notice("B000210", "1001", ROW)
    assert r is not None
    assert r["case_no"] == "2026타경101761"
    assert r["ordered_date"] == date(2026, 9, 15)
    assert r["claim_deadline"] == date(2026, 11, 27)
    assert r["notice_date"] == date(2026, 9, 18)
    assert (r["sido"], r["sigungu"], r["dong"], r["lot_no"]) == (
        "서울특별시",
        "관악구",
        "신림동",
        "1421-1",
    )
    assert r["building_detail"] == "8층809호"
    assert r["item_count"] is None
    assert "홍길동" not in str(r)  # 이름은 core 표에 넣지 않음


def test_parse_notice_no_case() -> None:
    assert parse_notice("B000210", "1001", {"userCsNo": " "}) is None


def test_dept_codes_skip_archive() -> None:
    rows = [{"code": "1001", "name": "경매1계"}, {"code": "B901", "name": "경매1계(보존)"},
            {"code": "1099", "name": "관리자"}]  # fmt: skip
    assert dept_codes(rows) == [("1001", "경매1계")]
