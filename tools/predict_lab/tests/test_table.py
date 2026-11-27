"""학습 표: 강사 자료 묶기 · 우리 자료 우선 · 거르기 · 용도 분류 · 주소의 지번."""

from datetime import date

from market import norm_name, parse_addr_jibun
from table import Geo, apply_filters, group_instructor, instructor_row, is_misbid, merge
from usage import EXCLUDED, class_of_name, classify, code_majority


def _raw(**kw):
    base = dict(
        boCd="B000210", saNo="20080130025092", srnSaNo="2008타경25092", maemulSer="1",
        maeGiil="20260730", gamevalAmt="194000000", minmaePrice="155200000", maeAmt="0",
        mulStatcd="03", yuchalCnt="3", dspslUsgNm="아파트", sclsUtilCd="20104",
        hjguSido="서울특별시", hjguSigu="성북구", hjguDong="정릉동", buldNm="", mulBigo="",
        maxArea="67", minArea="67", jiwonNm="서울중앙지방법원", jpDeptNm="경매2계",
    )  # fmt: skip
    base.update(kw)
    return base


def test_토지_건물_여러_줄은_한_줄로_묶인다():
    raw = [_raw(), _raw(dspslUsgNm="기타"), _raw(maemulSer="2")]
    grouped, conflicts = group_instructor(raw)
    assert len(grouped) == 2  # 물건 1번 · 2번
    assert conflicts == 0


def test_같은_묶음에서_금액이_다르면_충돌로_센다():
    grouped, conflicts = group_instructor([_raw(), _raw(gamevalAmt="1")])
    assert len(grouped) == 1 and conflicts == 1


def test_매각과_유찰_판정():
    geo = Geo({"11140": "서울특별시 성북구"}, {})
    sold = group_instructor([_raw(mulStatcd="04", maeAmt="42110000")])[0][0]
    failed = group_instructor([_raw()])[0][0]
    other = group_instructor([_raw(mulStatcd="05", maeAmt="0")])[0][0]
    results = {instructor_row(g, geo, {})["result"] for g in (sold, failed, other)}
    assert results == {"sold", "failed", "?"}


def test_우리_자료는_겹치는_물건을_이긴다():
    court = [
        {
            "court_code": "B1",
            "case_no": "2025타경1",
            "item_no": 1,
            "sale_date": date(2026, 10, 1),
            "src": "court",
        }
    ]
    ours = [
        {
            "court_code": "B1",
            "case_no": "2025타경1",
            "item_no": 1,
            "sale_date": date(2026, 10, 1),
            "src": "ours",
        }
    ]
    merged, stats = merge(court, ours)
    assert [r["src"] for r in merged] == ["ours"]
    assert stats["matched"] == 1 and stats["court_only"] == 0


def test_사건번호_모양만_다르면_맞춘_건수에서_뺀다():
    court = [
        {
            "court_code": "B1",
            "case_no": "2025-1",
            "item_no": 1,
            "sale_date": date(2026, 10, 1),
            "src": "court",
        }
    ]
    ours = [
        {
            "court_code": "B1",
            "case_no": "2025타경1",
            "item_no": 1,
            "sale_date": date(2026, 10, 1),
            "src": "ours",
        }
    ]
    merged, stats = merge(court, ours)
    assert stats["matched"] == 0 and stats["shape_mismatch_candidates"] == 1


def _row(**kw):
    base = dict(
        result="sold", category="아파트", appraisal_krw=100_000_000, min_price_krw=60_000_000,
        winning_bid_krw=70_000_000, sale_rate=70.0, sale_date=date(2026, 10, 1), is_share=False,
        is_special=False,
    )  # fmt: skip
    base.update(kw)
    return base


def test_거르기_지분_특수_자동차_입찰가_오기():
    rows = [
        _row(is_share=True),
        _row(is_special=True),
        _row(category=EXCLUDED),
        _row(category=None),
        _row(
            sale_rate=350.0, winning_bid_krw=700_000_000, min_price_krw=60_000_000
        ),  # 최저가의 10배 이상
        _row(),
    ]
    kept, dropped = apply_filters(rows)
    assert len(kept) == 1
    assert dropped["지분"] == 1 and dropped["특수"] == 1 and dropped["입찰가 오기"] == 1


def test_입찰가_오기_기준은_pro_와_같다():
    assert is_misbid(300.0, 600, 60)  # 300% 이상 · 최저가의 10배 이상
    assert not is_misbid(299.9, 600, 60)
    assert not is_misbid(350.0, 500, 60)


def test_용도_이름_분류():
    assert class_of_name("아파트") == "아파트"
    assert class_of_name("다세대,연립주택") == "빌라"
    assert class_of_name("상가,오피스텔,근린시설") == "상가"
    assert class_of_name("오피스텔") == "오피스텔"
    assert class_of_name("대지,임야,전답") == "땅"
    assert class_of_name("자동차,중기") == EXCLUDED
    assert class_of_name("기타") is None


def test_기타는_소분류_코드의_다수결로():
    code_map = code_majority(
        [("20104", "아파트"), ("20104", "아파트"), ("20104", "기타"), ("30101", "자동차")]
    )
    assert classify("기타", "20104", code_map) == "아파트"
    assert classify("기타", "30101", code_map) == EXCLUDED
    assert classify("기타", "99999", code_map) is None


def test_주소에서_법정동과_지번():
    assert parse_addr_jibun("경기도 안산시 상록구 부곡동 647-15 제이앤빌 3층302호") == (
        "부곡동",
        "647-15",
    )
    assert parse_addr_jibun(None) == (None, None)


def test_단지_이름_정규화():
    assert norm_name("제이 앤(빌) 1-2") == "제이앤빌12"


def test_화성시처럼_구가_빠진_이름은_법정동으로_고른다():
    names = {"41590": "경기도 화성시 동탄구", "41591": "경기도 화성시 병점구"}
    geo = Geo(names, {"41590": {"석우동"}, "41591": {"병점동"}})
    assert geo.sgg("경기도", "화성시", "병점동") == "41591"
    assert geo.sgg("경기도", "화성시", None) is None  # 법정동 없으면 못 고름
