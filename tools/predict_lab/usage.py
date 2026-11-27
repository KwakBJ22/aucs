"""용도 분류: 법원 용도 이름 → 종류(아파트 · 빌라 · 오피스텔 · 상가 · 땅 · 그 밖 · 제외).

법원 용도 이름은 「기타」가 많아, 「기타」이면 같은 소분류 코드(sclsUtilCd)에서 가장 많이 나온 종류를 쓴다.
자동차 · 중기 · 선박 같은 동산은 「제외」(부동산 통계에서 뺌 — pro.py 의 VEHICLES 와 같은 기준).
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable

CLASSES = ("아파트", "빌라", "오피스텔", "상가", "땅", "그 밖")
EXCLUDED = "제외"

_VEHICLE = re.compile(r"자동차|중기|선박")


def class_of_name(name: str | None) -> str | None:
    """용도 이름 하나 → 종류. 「기타」·빈 값은 None(모름)."""
    if not name or name.strip() in ("", "기타"):
        return None
    if _VEHICLE.search(name):
        return EXCLUDED
    first = name.split(",")[0].strip()  # 「상가,오피스텔,근린시설」처럼 묶인 이름은 앞 것으로
    if "아파트" in first:
        return "아파트"
    if re.search(r"다세대|연립|빌라", first):
        return "빌라"
    if "오피스텔" in first:
        return "오피스텔"
    if re.search(r"상가|근린", first):
        return "상가"
    if re.search(r"대지|임야|전답|잡종지", first):
        return "땅"
    return "그 밖"


def code_majority(pairs: Iterable[tuple[str | None, str | None]]) -> dict[str, str]:
    """(소분류 코드, 용도 이름) 쌍들로 코드 → 가장 많은 종류 표를 만든다(「기타」는 세지 않음)."""
    votes: dict[str, Counter] = defaultdict(Counter)
    for code, name in pairs:
        cls = class_of_name(name)
        if code and cls:
            votes[code][cls] += 1
    return {code: c.most_common(1)[0][0] for code, c in votes.items()}


def classify(name: str | None, code: str | None, code_map: dict[str, str]) -> str | None:
    """이름으로 못 정하면(「기타」) 소분류 코드 표로. 그래도 모르면 None."""
    cls = class_of_name(name)
    if cls is not None:
        return cls
    if code and code in code_map:
        return code_map[code]
    return None
