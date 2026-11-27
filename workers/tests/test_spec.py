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
