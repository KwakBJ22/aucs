"""법원 응답 한 줄을 우리 표 모양으로 바꿉니다 (순수 함수, 시험 대상)."""

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any

from aucs_workers.extract.mask import mask_names

KATEC = (
    "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 +ellps=bessel +units=m "
    "+towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43 +no_defs"
)
_transformer: Any = None


def checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def to_int(v: Any) -> int | None:
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def to_date(v: Any) -> date | None:
    try:
        return datetime.strptime(str(v), "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def katec_to_wgs84(x: Any, y: Any) -> tuple[float, float] | None:
    """법원 좌표(KATEC) → (위도, 경도). 2026-10-06 성북구 물건으로 검산한 식."""
    global _transformer
    fx, fy = to_int(x), to_int(y)
    if not fx or not fy:
        return None
    if _transformer is None:
        from pyproj import Transformer

        _transformer = Transformer.from_crs(KATEC, "EPSG:4326", always_xy=True)
    lon, lat = _transformer.transform(fx, fy)
    if 33 < lat < 39 and 124 < lon < 132:
        return round(lat, 6), round(lon, 6)
    return None


def area_sum(text: str | None) -> float | None:
    vals = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)㎡", text or "")]
    return round(sum(vals), 3) if vals else None


def split_sigungu(text: str | None) -> tuple[str | None, str | None]:
    """「용인시 수지구」 → (용인시, 수지구), 「강남구」 → (강남구, None)."""
    parts = (text or "").split()
    if not parts:
        return None, None
    if len(parts) > 1 and parts[0].endswith("시") and parts[1].endswith("구"):
        return parts[0], parts[1]
    return parts[0], None


def min_price(r: dict[str, Any]) -> int | None:
    """이번 기일 최저가 = 공고 최저가. minmaePrice 는 직전 회차 값일 때가 있음(10/7 확인)."""
    notified = to_int(r.get("notifyMinmaePrice1"))
    return notified if notified else to_int(r.get("minmaePrice"))


def ids(r: dict[str, Any]) -> tuple[str, str, int]:
    court, case_no = str(r["boCd"]), str(r["srnSaNo"])
    case_id = f"{court}-{case_no}"
    item_no = to_int(r.get("maemulSer")) or 1
    return case_id, f"{case_id}-{item_no}", item_no


def parse_item(r: dict[str, Any]) -> dict[str, Any]:
    """물건상세검색 한 줄 → 사건·물건·회차."""
    case_id, item_id, item_no = ids(r)
    sale_date = to_date(r.get("maeGiil"))
    sigungu, gu = split_sigungu(r.get("hjguSigu"))
    latlon = katec_to_wgs84(r.get("xCordi"), r.get("yCordi"))
    note = mask_names(r.get("mulBigo"))
    address = re.sub(r"^\s*(사용본거지|소재지)\s*:\s*", "", str(r.get("printSt") or "")).strip()
    item = {
        "item_id": item_id,
        "case_id": case_id,
        "item_no": item_no,
        "doc_key": r.get("docid"),
        "usage_name": r.get("dspslUsgNm"),
        "usage_code": r.get("sclsUtilCd"),
        "address": address or None,
        "region_code": r.get("srchHjguRdCd") or None,
        "sido": r.get("hjguSido") or None,
        "sigungu": sigungu,
        "gu": gu,
        "lot_no": r.get("srchHjguLotno") or None,
        "building_desc": " ".join(x for x in [r.get("buldNm"), r.get("buldList")] if x) or None,
        "building_area_m2": area_sum(r.get("pjbBuldList")),
        "appraisal_krw": to_int(r.get("gamevalAmt")),
        "min_price_krw": min_price(r),
        "failed_count": to_int(r.get("yuchalCnt")),
        "sale_date": sale_date,
        "sale_place": r.get("maePlace") or None,
        "status_code": r.get("mulStatcd"),
        "note_masked": note or None,
        "is_share": "지분" in note,
        "lat": latlon[0] if latlon else None,
        "lon": latlon[1] if latlon else None,
    }
    case = {
        "case_id": case_id,
        "court_code": r["boCd"],
        "case_no": r["srnSaNo"],
        "dept_name": r.get("jpDeptNm"),
    }
    rnd = None
    if sale_date:
        rnd = {
            "round_id": f"{item_id}-{sale_date:%Y%m%d}",
            "item_id": item_id,
            "sale_date": sale_date,
            "appraisal_krw": item["appraisal_krw"],
            "min_price_krw": item["min_price_krw"],
            "failed_count": item["failed_count"],
            "sale_place": item["sale_place"],
        }
    return {"case": case, "item": item, "round": rnd}


def parse_result(r: dict[str, Any]) -> dict[str, Any] | None:
    """매각결과검색 한 줄 → 매각결과. 01(진행 중)은 버림. 03 = 유찰, 그 밖 = 매각."""
    code = str(r.get("mulStatcd") or "")
    sale_date = to_date(r.get("maeGiil"))
    if code == "01" or not sale_date:
        return None
    case_id, item_id, item_no = ids(r)
    appraisal = to_int(r.get("gamevalAmt"))
    win = to_int(r.get("maeAmt")) or None
    sold = code != "03"
    sigungu, _ = split_sigungu(r.get("hjguSigu"))
    return {
        "court_code": r["boCd"],
        "case_no": r["srnSaNo"],
        "item_no": item_no,
        "sale_date": sale_date,
        "item_id": item_id,
        "usage_name": r.get("dspslUsgNm"),
        "address": str(r.get("printSt") or "").strip() or None,
        "sido": r.get("hjguSido") or None,
        "region_code": r.get("srchHjguRdCd") or None,
        "building_area_m2": area_sum(r.get("pjbBuldList")),
        "appraisal_krw": appraisal,
        "min_price_krw": min_price(r),
        "winning_bid_krw": win if sold else None,
        "sale_rate": round(win * 100 / appraisal, 1) if sold and win and appraisal else None,
        "failed_count": to_int(r.get("yuchalCnt")),
        "result": "sold" if sold else "failed",
        "is_share": "지분" in str(r.get("mulBigo") or ""),
    }
