"""감정평가서 원본 → 회사 이름 · 열람 주소 (11/4)."""

from aucs_workers.extract.appraisal_pdf import case_numbers, firm_name, points_from_pages


def test_firm_name() -> None:
    t = "감 정 평 가 서\n가람감정평가법인(주) 서울지사\n... 한국감정평가사협회 ... 가람감정평가법인(주)"
    assert firm_name(t) == "가람감정평가법인(주)"
    assert firm_name("본 평가서는 홍길동감정평가사사무소 에서") == "홍길동감정평가사사무소"
    assert firm_name("한국감정평가사협회") is None


def test_points_from_pages() -> None:
    head = " (1) 위치 및 주위환경 (2) 교통상황 (3) 건물의 구조\n구분건물 감정평가요항표\nYJ250708\n"
    p1 = (
        head
        + "Page : 1\n(1) 위치 및 주위환경\n본건은 문정중학교 인근에 소재하며,\n주위는 주택지대임.\n(2) 교통상황\n버스 정류장이 소재함.\n(6) 토지의 형상 및 이용상태\n일주감정평가사사무소\n"
    )
    p2 = (
        head
        + "Page : 2\n사다리형 토지임.\n(7) 인접 도로상태등\n약 5미터 폭의 포장도로에 접함.\n일주감정평가사사무소\n"
    )
    got = {
        e["aeeWevlMnpntItmCd"]: e["aeeWevlMnpntCtt"] for e in points_from_pages(["표지", p1, p2])
    }
    assert got["00083001"] == "본건은 문정중학교 인근에 소재하며, 주위는 주택지대임."
    assert got["00083008"] == "사다리형 토지임."  # 쪽이 넘어가도 이어 붙음
    assert got["00083004"] == "약 5미터 폭의 포장도로에 접함."
    assert got["00083003"] == "버스 정류장이 소재함."
    assert points_from_pages(["요항표 없는 글"]) == []
    # 「1. 제목」 꼴 + 쪽 맨 위 차례가 줄마다 따로인 회사
    q = "(토지) 감정평가요항표\n- 22 -\n1. 위치 및 주위환경\n4. 인접 도로상태\n2. 교통상황\n1. 위치 및 주위환경\n천문대 인근임.\n2. 교통상황\n보통임.\n"
    got = {e["aeeWevlMnpntItmCd"]: e["aeeWevlMnpntCtt"] for e in points_from_pages([q])}
    assert got == {"00083001": "천문대 인근임.", "00083003": "보통임."}


def test_case_numbers() -> None:
    assert case_numbers("소유물건 (2025 타경 56683) ... 2025타경56683") == ["2025타경56683"]


def test_swapped_case_number_and_report_no() -> None:
    """「(2025타경59003)」이 「타경(2025 59003)」으로 뽑히는 PDF(11/14) · 감정평가서 번호로도 가름."""
    from aucs_workers.extract.appraisal_pdf import has_report_no, same_case

    head = "건 명 : 소유물건\n타경(2025 59003)\n감정평가서 번호 : SR2511-01-012"
    assert case_numbers(head) == ["2025타경59003"]
    assert same_case(head, "2025타경59003") and not same_case(head, "2025타경5900")
    assert (
        has_report_no(head, "SR2511-01-012")
        and not has_report_no(head, "SR25")
        and not has_report_no(head, None)
    )
