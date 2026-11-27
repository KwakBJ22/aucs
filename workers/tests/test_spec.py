"""매각물건명세서 원본 글 → 임차인 줄(11/26 지시 1126a). 낱말은 법원 뷰어(streamdocs) 쪽 글을 words_from_texts 로 바꾼 것."""

import json
from datetime import date
from pathlib import Path

from aucs_workers.extract.spec import parse_tenants, words_from_texts

FX = Path(__file__).parent / "fixtures"


def _rows(name: str) -> list[dict]:
    ws = [tuple(w) for w in json.loads((FX / name).read_text(encoding="utf-8"))]
    return parse_tenants(ws)["rows"]  # type: ignore[arg-type]


def test_heir_merged_and_foreigners() -> None:
    # 서울동부 2025타경51836: 김은(등기 임차권 5.15억) + 한국주택금융공사(임차인:김은, 권리신고) → 한 줄
    rows = _rows("spec_words_51836.json")
    assert [r["name"] for r in rows] == ["BAYAR AA N*****", "THOMS EN A*****", "김은", "양승하"]
    kim = rows[2]
    assert kim["deposit_krw"] == 515_000_000 and kim["move_in_date"] == date(2022, 7, 5)
    assert kim["fixed_date"] == date(2022, 6, 7) and kim["claim_date"] == date(2025, 7, 23)
    assert rows[3]["deposit_krw"] == 5_000_000 and rows[3]["move_in_date"] == date(2025, 6, 13)


def test_same_person_two_sources() -> None:
    # 서울중앙 2026타경100740: 임세은 등기사항전부증명서 · 권리신고 두 줄(이름 칸 하나) → 한 줄, 보증금 한 번
    rows = _rows("spec_words_100740.json")
    assert [r["name"] for r in rows] == ["권지수", "임세은"]
    assert rows[0]["deposit_krw"] == 500_000 and rows[0]["monthly_rent_krw"] == 957_000
    im = rows[1]
    assert im["deposit_krw"] == 240_000_000 and im["claim_date"] == date(2026, 4, 10)
    assert im["move_in_date"] == date(2022, 3, 22) and im["fixed_date"] == date(2022, 2, 28)


def test_no_tenants_and_words() -> None:
    pages = {
        0: [
            {
                "text": "조사된 임차내역없음",
                "rect": [
                    {"left": 200 + i * 5, "right": 205 + i * 5, "top": 480} for i in range(10)
                ],
            }
        ]
    }
    ws = words_from_texts(pages)
    assert [w[4] for w in ws] == ["조사된", "임차내역없음"]
    assert parse_tenants(ws) == {"none": True, "rows": []}


def test_date_split_over_lines() -> None:
    # 성남 2025타경52870: 확정일자 「(1)2022.08.1」 / 「0.」 두 줄 → 2022-08-10(08-01 로 읽었음, 11/27)
    from aucs_workers.extract.spec import DATE, _join_dates

    t = _join_dates(["(1)2022.08.1", "0.", "(2)2022.11.0", "1."])
    assert DATE.findall(t) == ["2022.08.10", "2022.11.01"]
    assert _join_dates(["2025.", "6.5."]) == "2025.6.5."
    assert _join_dates(["미상"]) == "미상"


def test_fix_split_guarantor_names() -> None:
    from aucs_workers.extract.spec import fix_names, merge_same

    d = date(2022, 12, 16)
    base = {"part": "910호", "source": None, "title": None, "period": None, "monthly_rent_krw": None,
            "fixed_date": None, "claim_date": None, "claim_text": None}  # fmt: skip
    rows = [
        {**base, "name": "유현성한국주택금융", "deposit_krw": 125_000_000, "move_in_date": d},
        {**base, "name": "공사(임차인:유현성)", "deposit_krw": 125_000_000, "move_in_date": d,
         "claim_date": date(2025, 8, 22)},
        {**base, "name": None, "deposit_krw": 30_000_000, "move_in_date": date(2018, 9, 27)},
        {**base, "name": "변병림", "deposit_krw": 30_000_000, "move_in_date": date(2018, 9, 27)},
    ]  # fmt: skip
    fixed = fix_names(rows)
    assert [r["name"] for r in fixed] == ["유현성", "한국주택금융공사(임차인:유현성)", "변병림", "변병림"]
    out = merge_same(fixed)
    assert [r["name"] for r in out] == ["유현성", "변병림"]
    assert out[0]["claim_date"] == date(2025, 8, 22)


def test_same_name_unknown_deposit_merged() -> None:
    from aucs_workers.extract.spec import fix_names, merge_same

    d = date(2018, 9, 27)
    base = {"part": None, "source": None, "title": None, "period": None, "monthly_rent_krw": None,
            "fixed_date": None, "claim_date": None, "claim_text": None}  # fmt: skip
    rows = [{**base, "name": None, "deposit_krw": 30_000_000, "move_in_date": d},
            {**base, "name": "변병림", "deposit_krw": None, "move_in_date": d, "source": "현황조사"},
            {**base, "name": "변병림", "deposit_krw": 30_000_000, "move_in_date": d, "source": "권리신고"},
            {**base, "name": "장소희", "deposit_krw": None, "move_in_date": date(2025, 3, 4)}]  # fmt: skip
    out = merge_same(fix_names(rows))
    assert [(r["name"], r["deposit_krw"]) for r in out] == [("변병림", 30_000_000), ("장소희", None)]


def test_lists_to_items() -> None:
    # 서울남부 2025타경548: 물건 1 = 목록 1~7(11층), 물건 2 = 목록 8~14(12층)
    from aucs_workers.extract.case_docs import lists_to_items

    det = {1: {"dma_result": {"gdsDspslObjctLst": [{"dspslObjctSeq": str(i)} for i in range(1, 8)]}},
           2: {"dma_result": {"gdsDspslObjctLst": [{"dspslObjctSeq": i} for i in range(8, 15)]}}}  # fmt: skip
    m = lists_to_items(det)
    assert m[2] == 1 and m[7] == 1 and m[8] == 2 and m[14] == 2 and 15 not in m


def test_two_rows_in_one_cell() -> None:
    from aucs_workers.extract.spec import _money, fix_names

    assert _money(["250,000,000", "250,000,000"]) == 250_000_000
    assert _money(["18,000,000"]) == 18_000_000 and _money([]) is None
    base = {"part": None, "source": None, "title": None, "period": None, "monthly_rent_krw": None,
            "fixed_date": None, "claim_date": None, "claim_text": None, "move_in_date": None}  # fmt: skip
    rows = fix_names([{**base, "name": "박종민주택도시보증공사(박종민)", "deposit_krw": 226_000_000}])
    assert rows[0]["name"] == "박종민"
