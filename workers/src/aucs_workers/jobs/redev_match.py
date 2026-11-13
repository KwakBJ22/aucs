"""경매 물건 ↔ 서울 정비사업(정보몽땅) 잇기.

구역 경계 자료가 없어 두 가지만 확실하게 봅니다.
1) 대표지번이 물건 지번과 같음(같은 구·동)
2) 재건축·리모델링 단지 이름이 물건 건물 이름에 들어 있음(같은 구·동, 이름 3글자 이상)
구역 안 다른 지번은 못 잡습니다 — 토지이용계획(vworld)을 붙이면 보완.
"""

import re
from typing import Any

from aucs_rules.location import zone_usable

_STRIP = re.compile(
    r"\s|\(.*?\)|아파트.*$|주택재건축.*$|재건축.*$|정비사업.*$|조합.*$|리모델링.*$|추진위.*$"
)


def zone_key(name: str) -> str | None:
    """단지 이름 열쇠: 「뉴서울아파트, 개나리 … 재건축정비사업」 → 「뉴서울」."""
    k = _STRIP.sub("", name.split(",")[0])
    k = re.sub(r"[0-9]+차$", "", k)
    if len(k) < 3 or re.search(r"(구|역)$", k) or re.search(r"[0-9]", k):
        return None
    return k


def dong_of(address: str | None) -> str | None:
    m = re.search(r"\s([가-힣0-9]+동[0-9]*가?)\s", address or "")
    return m.group(1) if m else None


def lot_parts(lot_no: str | None) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", (lot_no or "").strip())
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def usable(z: dict[str, Any]) -> bool:
    return zone_usable(z.get("stage"), z.get("biz_type"))  # 판단은 규칙 한 곳(LOC-01, 11/13)


def pick(item: dict[str, Any], zones: list[dict[str, Any]]) -> dict[str, Any] | None:
    """같은 구·동 정비사업 목록에서 물건과 맞는 것 하나 (순수 함수)."""
    lot = lot_parts(item.get("lot_no"))
    bname = re.sub(r"\s", "", item.get("building_desc") or "")
    for z in zones:
        if not usable(z):
            continue
        if lot and (z.get("main_no"), z.get("sub_no") or 0) == lot:
            return {**z, "how": "지번"}
    for z in zones:
        if not usable(z) or not re.search("재건축|리모델링", z.get("biz_type") or ""):
            continue
        k = zone_key(z["name"])
        if (
            k and k != z.get("dong_name") and k in bname
        ):  # 「역삼동」 같은 동 이름은 단지 이름이 아님
            return {**z, "how": "단지 이름"}
    return None


def find_zone(cur: Any, item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("sido") != "서울특별시":
        return None
    dong = dong_of(item.get("address"))
    if not dong:
        return None
    rows = cur.execute(
        """select name, biz_type, stage, main_no, sub_no, dong_name from ref.redev_zones
           where gu = %s and dong_name = %s order by source = '사업장 목록' desc, zone_id""",
        (item.get("sigungu"), dong),
    ).fetchall()
    zones = [
        r
        if isinstance(r, dict)
        else dict(
            zip(("name", "biz_type", "stage", "main_no", "sub_no", "dong_name"), r, strict=True)
        )
        for r in rows
    ]
    z = pick(item, zones)
    if not z:
        return None
    return {k: z.get(k) for k in ("name", "biz_type", "stage", "how")}
