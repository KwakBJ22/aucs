"""올린 등기부의 소재지가 이 물건과 같은지 (순수 함수).

등기부는 지번 주소(「제304동 제2층 제203호」), 물건은 법원 표기(「304동 2층203호」)라
띄어쓰기·「제」·「특별시」를 떼고 시·군·구, 지번(본번-부번), 동·호 숫자로 맞춥니다.
글자 인식이 「동」을 「농」으로 읽는 일이 있어 둘 다 받습니다.
"""

import re
from typing import Any

_UNIT_DONG = re.compile(r"제?\s*(\d{1,4})\s*[동농](?!\d)")
_UNIT_HO = re.compile(r"제?\s*(\d{1,5})\s*호")
_LOT = re.compile(r"(?:^|\s)(?:산\s*)?(\d{1,5}(?:-\d{1,5})?)(?:번지)?(?=\s|$)")
_GU = re.compile(r"([가-힣]{1,6}(?:시|군|구))(?=\s)")


def _units(addr: str) -> tuple[str | None, str | None]:
    tail = addr.split()[-4:]  # 단지명 뒤쪽만 봄 (「성복동」 같은 동네 이름 숫자 없음)
    t = " ".join(tail)
    d = _UNIT_DONG.findall(t)
    h = _UNIT_HO.findall(t)
    return (d[-1].lstrip("0") if d else None), (h[-1].lstrip("0") if h else None)


def _lot(addr: str) -> str | None:
    m = _LOT.search(addr)
    return m.group(1) if m else None


def compare(registry_addr: str | None, item_addr: str | None) -> dict[str, Any]:
    """same / unit_differs / different / unknown 과 비교에 쓴 값."""
    if not registry_addr or not item_addr:
        return {"result": "unknown"}
    r, i = registry_addr.strip(), item_addr.strip()
    r_gu, i_gu = set(_GU.findall(r + " ")), set(_GU.findall(i + " "))
    r_lot, i_lot = _lot(r), _lot(i)
    (r_d, r_h), (i_d, i_h) = _units(r), _units(i)
    out = {"registry": r, "item": i, "registry_unit": _fmt(r_d, r_h), "item_unit": _fmt(i_d, i_h)}
    if r_gu and i_gu and not (r_gu & i_gu):
        return {**out, "result": "different"}
    if r_lot and i_lot and r_lot != i_lot:
        return {**out, "result": "different"}
    if (r_h and i_h and r_h != i_h) or (r_d and i_d and r_d != i_d):
        return {**out, "result": "unit_differs"}
    if r_lot and i_lot:  # 지번 같고 동·호도 어긋나지 않음
        return {**out, "result": "same"}
    return {**out, "result": "unknown"}


def _fmt(d: str | None, h: str | None) -> str | None:
    if not d and not h:
        return None
    return " ".join(x for x in [f"{d}동" if d else None, f"{h}호" if h else None] if x)
