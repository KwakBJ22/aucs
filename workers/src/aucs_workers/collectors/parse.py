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
    # 법원 자료는 「147.8405 ㎡」처럼 띄어 쓰거나 줄을 바꿔 오는 일이 많음 (10/19: 건물 290건 면적이 비었던 원인)
    vals = [
        float(x.replace(",", ""))
        for x in re.findall(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*㎡", text or "")
    ]
    return round(sum(vals), 3) if vals else None


def building_area(r: dict[str, Any]) -> float | None:
    """건물 면적: 건물 목록 → 비었으면 집합건물·건물일 때만 면적 목록(땅만 있는 물건은 비워 둠)."""
    area = area_sum(r.get("pjbBuldList"))
    if area is None and re.match(r"\[(집합건물|건물)", str(r.get("convAddr") or "")):
        area = area_sum(r.get("areaList"))
    return area


def split_sigungu(text: str | None) -> tuple[str | None, str | None]:
    """「용인시 수지구」 → (용인시, 수지구), 「강남구」 → (강남구, None)."""
    parts = (text or "").split()
    if not parts:
        return None, None
    if len(parts) > 1 and parts[0].endswith("시") and parts[1].endswith("구"):
        return parts[0], parts[1]
    return parts[0], None


SIDO_ALIAS = {
    "서울": "서울특별시", "서울시": "서울특별시", "서울특별시": "서울특별시",
    "경기": "경기도", "경기도": "경기도", "인천": "인천광역시", "인천시": "인천광역시", "인천광역시": "인천광역시",
    "부산": "부산광역시", "부산광역시": "부산광역시", "대구": "대구광역시", "대구광역시": "대구광역시",
    "광주": "광주광역시", "광주광역시": "광주광역시", "대전": "대전광역시", "대전광역시": "대전광역시",
    "울산": "울산광역시", "울산광역시": "울산광역시", "세종": "세종특별자치시", "세종특별자치시": "세종특별자치시",
    "강원": "강원특별자치도", "강원도": "강원특별자치도", "강원특별자치도": "강원특별자치도",
    "충북": "충청북도", "충청북도": "충청북도", "충남": "충청남도", "충청남도": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전북특별자치도": "전북특별자치도",
    "전남": "전라남도", "전라남도": "전라남도", "경북": "경상북도", "경상북도": "경상북도",
    "경남": "경상남도", "경상남도": "경상남도", "제주": "제주특별자치도", "제주특별자치도": "제주특별자치도",
}  # fmt: skip
GYEONGGI_CITIES = {
    "수원시", "성남시", "의정부시", "안양시", "부천시", "광명시", "평택시", "동두천시", "안산시", "고양시",
    "과천시", "구리시", "남양주시", "오산시", "시흥시", "군포시", "의왕시", "하남시", "용인시", "파주시",
    "이천시", "안성시", "김포시", "화성시", "광주시", "양주시", "포천시", "여주시", "연천군", "가평군", "양평군",
}  # fmt: skip


def region_from(
    sido: str | None, sigungu_text: str | None, address: str | None
) -> tuple[str | None, str | None, str | None]:
    """(시도, 시군구, 구). 법원 칸(hjgu)을 우선 쓰고, 그 칸이 망가졌을 때만 주소로 바로잡습니다.

    법원 칸 시도가 「서울」처럼 줄임말이면 정식 이름으로. 시도 칸에 「용인시」 같은 시 이름이 들어왔거나
    시군구 칸이 길 이름(…로·…길)이면 망가진 것으로 보고 주소(printSt)로 끊습니다.
    자동차 등은 주소가 사용본거지라 법원 칸이 멀쩡하면 주소를 쓰지 않습니다.
    """
    sg_text = (sigungu_text or "").strip()
    broken = (
        sido not in SIDO_ALIAS
        or not sg_text
        or sg_text.split()[0].endswith(("로", "길", "읍", "면"))
    )
    if not broken:
        sg, gu = split_sigungu(sg_text)
        return SIDO_ALIAS[sido or ""], sg, gu
    words = (address or "").replace(",", " ").split()
    if words and words[0] in SIDO_ALIAS:
        sg, gu = split_sigungu(" ".join(words[1:3]))
        return SIDO_ALIAS[words[0]], sg, gu
    if words and words[0] in GYEONGGI_CITIES:
        sg, gu = split_sigungu(" ".join(words[0:2]))
        return "경기도", sg, gu
    if sido in GYEONGGI_CITIES:
        gu = sg_text if sg_text.endswith("구") else None
        return "경기도", sido, gu
    sg, gu = split_sigungu(sg_text)
    return SIDO_ALIAS.get(sido or "", sido), sg, gu


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
    latlon = katec_to_wgs84(r.get("xCordi"), r.get("yCordi"))
    note = mask_names(r.get("mulBigo"))
    address = re.sub(r"^\s*(사용본거지|소재지)\s*:\s*", "", str(r.get("printSt") or "")).strip()
    sido, sigungu, gu = region_from(r.get("hjguSido") or None, r.get("hjguSigu"), address)
    item = {
        "item_id": item_id,
        "case_id": case_id,
        "item_no": item_no,
        "doc_key": r.get("docid"),
        "usage_name": r.get("dspslUsgNm"),
        "usage_code": r.get("sclsUtilCd"),
        "address": address or None,
        "region_code": r.get("srchHjguRdCd") or None,
        "sido": sido,
        "sigungu": sigungu,
        "gu": gu,
        "lot_no": r.get("srchHjguLotno") or None,
        "building_desc": " ".join(x for x in [r.get("buldNm"), r.get("buldList")] if x) or None,
        "building_area_m2": building_area(r),
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
    sido, sigungu, _ = region_from(
        r.get("hjguSido") or None, r.get("hjguSigu"), str(r.get("printSt") or "")
    )
    return {
        "court_code": r["boCd"],
        "case_no": r["srnSaNo"],
        "item_no": item_no,
        "sale_date": sale_date,
        "item_id": item_id,
        "usage_name": r.get("dspslUsgNm"),
        "address": str(r.get("printSt") or "").strip() or None,
        "sido": sido,
        "region_code": r.get("srchHjguRdCd") or None,
        "building_area_m2": building_area(r),
        "appraisal_krw": appraisal,
        "min_price_krw": min_price(r),
        "winning_bid_krw": win if sold else None,
        "sale_rate": round(win * 100 / appraisal, 1) if sold and win and appraisal else None,
        "failed_count": to_int(r.get("yuchalCnt")),
        "result": "sold" if sold else "failed",
        "is_share": "지분" in str(r.get("mulBigo") or ""),
    }
