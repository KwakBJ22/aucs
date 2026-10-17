"""문건·송달 내역 분류 (25분류 + 기타) 와 중요도.

지금 시스템의 SQL 뷰(경매_문건흐름)를 그대로 옮겼습니다. 위에서부터 처음 맞는 분류를 씁니다.
"""

import re
from datetime import date

# (분류, 정규식, 접수만?) — 순서가 중요합니다
_RULES: list[tuple[str, str, bool]] = [
    ("매각기일 통지", r"매각.*기일.*통지서", False),  # 받는 사람 이름에 낚이지 않게 먼저
    ("회생·파산", r"회생|파산", False),
    ("매각조건 변경", r"인수조건|매각조건|특별매각조건", False),
    ("정지·취하 시도", r"정지신청|집행정지|정지결정|취하서|취하신청|취소신청", False),
    ("경매 속행 신청", r"속행", False),
    ("유치권 신고", r"유치권\s*(신고|권리신고)", False),
    ("공유자 우선매수", r"공유자우선매수|공유자 우선매수|우선매수신고", False),
    ("채권자 바뀜", r"채권자변경|명의변경|승계통지|승계집행문|채권양도", False),
    ("질권 신고", r"질권\s*신고|질권자 권리신고", False),
    ("권리신고·배당요구", r"(권리신고|배당요구)\s*(서|신청|및)|채권계산서|채권신고서", True),
    ("세금 교부청구", r"교부청구", False),
    ("배당 합의", r"우선배당|합의서|동의서", False),
    ("기일 연기·변경 신청", r"연기신청|변경신청", False),
    ("기일 지정 신청", r"기일지정", False),
    ("매각·대금·배당", r"매각허가|불허가|대금|배당기일|배당표", False),
    ("입찰 진행", r"기일입찰조서", False),
    ("경매 개시", r"개시결정정본", False),
    ("감정", r"감정평가서|평가명령|회보서|감정료", False),
    ("현황조사", r"현황조사|조사명령", False),
    ("이해관계인 최고", r"최고서", False),
    ("임차인 통지", r"임차인통지서", False),
    ("서류 보정", r"보정", False),
    ("대리인·송달장소", r"소송위임장|담당변호사|송달장소|송달영수인", False),
    ("의견서", r"의견서", False),
    ("서류 열람", r"열람", False),
    ("등기", r"등기", False),
]
_COMPILED = [(name, re.compile(p, re.S), only_receipt) for name, p, only_receipt in _RULES]

HIGH = {"회생·파산", "정지·취하 시도", "유치권 신고", "공유자 우선매수", "매각조건 변경"}
MID = {
    "경매 속행 신청",
    "채권자 바뀜",
    "권리신고·배당요구",
    "세금 교부청구",
    "기일 연기·변경 신청",
    "매각·대금·배당",
}


def classify(text: str, kind: str) -> str:
    """kind: 접수 / 송달."""
    for name, pat, only_receipt in _COMPILED:
        if only_receipt and kind != "접수":
            continue
        if pat.search(text or ""):
            return name
    return "기타"


def importance(
    category: str, event_date: date | None, claim_deadline: date | None
) -> tuple[str, bool]:
    """(중요도 high/mid/low, 종기 뒤 신고 여부)."""
    late = category == "권리신고·배당요구" and bool(
        event_date and claim_deadline and event_date > claim_deadline
    )
    if category in HIGH or late:
        return "high", late
    if category in MID:
        return "mid", late
    return "low", late
