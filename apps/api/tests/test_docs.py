from aucs_api.services.docs import deliveries, status_report

SR = {
    "dma_curstExmnMngInf": {"exmnDtDts": "2025년04월28일10시10분 ",
                            "printRltnDts": "본건 부동산의 현황은 외관상 공부의 내용과 일치하는 것으로 보임.",
                            "lesDts": "전입세대확인서, 주민등록등본에 근거하여 작성함."},
    "dlt_ordTsRlet": [{"gdsPossCtt": "폐문부재로 만날 수 없어 안내문을 부착함.<br />"}],
    "dlt_ordTsLserLtn": [{"intrpsNm": "임원", "mvinDtlCtt": "2021.04.01.", "lesDposDts": None}],
}  # fmt: skip


def test_status_report_masks_and_cleans():
    r = status_report(SR)
    assert r["exam_at"] == "2025년04월28일10시10분"
    assert r["possession"] == ["폐문부재로 만날 수 없어 안내문을 부착함."]
    assert r["tenants"][0]["name"] == "임○" and r["tenants"][0]["move_in"] == "2021.04.01."


def test_deliveries_marks_key_and_hides_appraisal():
    p = {
        "dlt_ofdocDtsLst": [
            {"rcptDts": "임차인 임OO 권리신고및배당요구신청서 제출", "ofdocRcptYmd": "20250520"},
            {"rcptDts": "감정인 (주)OOO 감정평가서 제출", "ofdocRcptYmd": "20250501"},
            {"rcptDts": "등기소 용OOOO 등기필증 제출", "ofdocRcptYmd": "20250421"},
        ],
        "dlt_dlvrDtsLst": [{"dlvrDts": "채무자겸소유자 임OO 개시결정정본 발송", "dlvrbkRegYmd": "20250422",
                            "lastDlvrblRchYmd": "2025.04.24 도달"}],
    }  # fmt: skip
    r = deliveries(p)
    assert [f["key"] for f in r["filings"]] == [True, False, False]
    assert r["filings"][1]["text"] == "감정인 서류 제출"
    assert r["filings"][0]["date"] == "2025-05-20"
    assert r["sends"][0]["result"] == "2025.04.24 도달"
