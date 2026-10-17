"""등기 권리 종류의 글자 인식 오류 보정 사전. 사전에 없으면 None(→ 확인 필요)."""

# 보정 전 → 표준 이름. 새로 발견한 오류는 여기에 추가하고 시험 사례도 추가합니다.
_FIX = {
    "가암큐": "가압류",
    "가압큐": "가압류",
    "가앞류": "가압류",
    "근저당권섣정": "근저당권설정",
    "근져당권설정": "근저당권설정",
    "압휴": "압류",
}

STANDARD = {
    "근저당권설정": "mortgage",
    "저당권설정": "mortgage",
    "압류": "seizure",
    "가압류": "provisional_seizure",
    "담보가등기": "security_provisional_registration",
    "임의경매개시결정": "auction_start",
    "강제경매개시결정": "auction_start",
    "전세권설정": "jeonse",
    "지상권설정": "superficies",
    "지역권설정": "servitude",
    "가처분": "injunction",
    "소유권이전청구권가등기": "transfer_claim_provisional_registration",
    "임차권설정": "lease_right",
    "주택임차권": "lease_right",
    "소유권이전": "ownership",
    "소유권보존": "ownership",
}


def normalize_purpose(text: str) -> str | None:
    """등기목적 글자 → 표준 이름(한글). 모르면 None."""
    t = "".join((text or "").split())
    t = _FIX.get(t, t)
    for name in sorted(STANDARD, key=len, reverse=True):
        if t.startswith(name) or t == name:
            return name
    return None


def kind_of(text: str) -> str | None:
    """등기목적 → 규칙에서 쓰는 종류 코드."""
    name = normalize_purpose(text)
    return STANDARD.get(name) if name else None
