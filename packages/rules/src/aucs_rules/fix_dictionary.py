"""등기 목적의 글자 인식 오류 보정과 종류 판별.

1) 앞에 붙은 「13번○○지분」 같은 대상 표시를 떼고
2) 보정 사전으로 알려진 오타를 고친 뒤
3) 표준 이름 목록과 맞춥니다. 끝까지 모르면 None → 「확인 필요」 (「기타」로 묶지 않음).
새로 발견한 오타는 _FIX 에 넣고 시험 사례도 추가합니다.
"""

import re
from difflib import SequenceMatcher

_FIX = {
    "가암큐": "가압류",
    "가압큐": "가압류",
    "가앞류": "가압류",
    "압튜": "압류",
    "주텍임차권": "주택임차권",
    "근저당권섣정": "근저당권설정",
    "근져당권설정": "근저당권설정",
    "페지": "폐지",
}

# 표준 이름 → 종류 코드 (긴 것부터 맞춤)
STANDARD = {
    "소유권이전청구권가등기": "transfer_claim_provisional_registration",
    "소유권이전담보가등기": "security_provisional_registration",
    "담보가등기": "security_provisional_registration",
    "가등기": "transfer_claim_provisional_registration",
    "근저당권부채권근질권설정": "pledge",
    "근저당권부채권질권설정": "pledge",
    "근저당권이전": "mortgage_transfer",
    "근저당권변경": "change",
    "근저당권설정": "mortgage",
    "저당권설정": "mortgage",
    "전세권설정": "jeonse",
    "상가건물임차권": "lease_right",
    "주택임차권": "lease_right",
    "임차권설정": "lease_right",
    "임차권": "lease_right",
    "구분지상권설정": "superficies",
    "지상권설정": "superficies",
    "지역권설정": "servitude",
    "임의경매개시결정": "auction_start",
    "강제경매개시결정": "auction_start",
    "가압류": "provisional_seizure",
    "압류": "seizure",
    "가처분": "injunction",
    "예고등기": "notice_registration",
    "환매특약": "repurchase",
    "신탁": "trust",
    "회생절차폐지": "rehab",
    "회생절차개시": "rehab",
    "파산선고": "rehab",
    "소유권일부이전": "ownership",
    "소유권이전": "ownership",
    "소유권보존": "ownership",
}
_SUFFIX_CHANGE = re.compile(r"(말소|변경|경정)$")


def clean_purpose(text: str) -> str:
    """공백 제거, 앞의 「N번…지분」 떼기, 오타 고치기."""
    t = re.sub(r"\s+", "", text or "")
    t = re.sub(r"^[^가-힣0-9]*", "", t)  # 앞쪽 인식 찌꺼기
    t = re.sub(
        r"^(?:,?\d+(?:-\d+)?번[가-힣○]*?지분(?:전부|\d+분의\d+)?(?:중일부\(?\d*분의\d*\)?)?)+",
        "",
        t,
    )
    if t == "이전":  # 「11번○○지분전부이전」 = 지분 소유권 이전
        t = "소유권일부이전"
    for wrong, right in _FIX.items():
        t = t.replace(wrong, right)
    return t


def normalize_purpose(text: str) -> str | None:
    """등기목적 글자 → 표준 이름(한글). 모르면 None."""
    t = clean_purpose(text)
    if not t:
        return None
    if _SUFFIX_CHANGE.search(t) and not t.endswith("등기말소"):
        return "변경·말소"
    for name in sorted(STANDARD, key=len, reverse=True):
        if t.endswith(name) or t == name:
            return name
    t2 = re.sub(r"^\d+(?:-\d+)?번", "", t)  # 「14번가압류」 같은 부기 대상 표시
    for name in sorted(STANDARD, key=len, reverse=True):
        if t2.endswith(name):
            return name
    return None


def kind_of(text: str) -> str | None:
    """등기목적 → 규칙에서 쓰는 종류 코드."""
    name = normalize_purpose(text)
    if name == "변경·말소":
        return "change"
    return STANDARD.get(name) if name else None


# ── 규칙으로 추정 (AI 없이) ──────────────────────────────
# 보정 사전에도 없는 오타를, 글자 모양(자모)이 비슷한 표준 이름과 권리자 종류로 추정합니다.
# 결과는 늘 「추정」으로 표시하고, 손님이 직접 고칠 수 있게 합니다. (10/18 대표님: AI 없이, 나중에 유료 글자 인식으로)

# 을구에만 오는 종류 (나머지는 갑구)
_EUL_KINDS = {
    "mortgage",
    "jeonse",
    "lease_right",
    "superficies",
    "servitude",
    "pledge",
    "mortgage_transfer",
}
# 지자체·세무서·공단 → 갑구라면 세금·보험료 압류가 거의 전부
_GOV = re.compile(
    r"(시|군|구|도|세무서|국민건강보험공단|국민연금공단|근로복지공단|대한민국|관리공단)$"
)
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
GUESS_MIN = 0.75


def _jamo(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out += [_CHO[code // 588], _JUNG[code % 588 // 28], _JONG[code % 28].strip()]
        else:
            out.append(ch)
    return "".join(out)


def names_for(section: str) -> list[str]:
    """그 구(갑·을)에 올 수 있는 표준 이름 (손님이 고를 목록)."""
    eul = section == "을"
    return [n for n, k in STANDARD.items() if (k in _EUL_KINDS) == eul]


def guess_purpose(text: str, section: str, holder: str = "") -> str | None:
    """보정 사전으로도 모르는 등기목적을 추정. 자신 없으면 None (→ 확인 필요)."""
    if normalize_purpose(text):
        return normalize_purpose(text)
    t = _jamo(re.sub(r"[^가-힣]", "", clean_purpose(text)))
    if not t:
        return None
    gov = bool(_GOV.search((holder or "").strip()))
    best, score = None, 0.0
    for name in names_for(section):
        j = _jamo(name)
        tail = t[-len(j) :]
        r = SequenceMatcher(None, tail, j).ratio()
        if gov and section == "갑" and name == "압류":
            r += 0.1
        if r > score:
            best, score = name, r
    return best if score >= GUESS_MIN else None
