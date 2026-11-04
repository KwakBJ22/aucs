"""감정평가서 원본 → 회사 이름 · 열람 주소 (11/4)."""

from aucs_workers.collectors.kapa_pdf import view_url
from aucs_workers.extract.appraisal_pdf import firm_name


def test_firm_name() -> None:
    t = "감 정 평 가 서\n가람감정평가법인(주) 서울지사\n... 한국감정평가사협회 ... 가람감정평가법인(주)"
    assert firm_name(t) == "가람감정평가법인(주)"
    assert firm_name("본 평가서는 홍길동감정평가사사무소 에서") == "홍길동감정평가사사무소"
    assert firm_name("한국감정평가사협회") is None


def test_view_url_same_as_court_popup() -> None:
    info = {"cortOfcCd": "B000210", "csNo": "20220130101244", "ordTsCnt": 1,
            "aeeWevlNo": "WJ-02-20220314-01", "wrtYmd": "20220324"}  # fmt: skip
    assert (
        view_url(info)
        == "https://ca.kapanet.or.kr/view/000210/20220130101244/1/WJ-02-20220314-01/20220324"
    )
    assert view_url({**info, "aeeWevlNo": None}) is None
