"""학습 표 만들기 (순수 함수): 강사 법원 자료 · 우리 자료를 한 줄(낙찰 · 유찰 한 건)씩 모은다.

- 강사 자료: 한 물건이 토지 · 건물 여러 줄 → (boCd, saNo, maemulSer, maeGiil) 로 한 줄. 매각 = 낙찰가 > 0.
- 우리 자료: core.sale_results. 겹치는 물건(같은 법원 · 사건 · 물건번호 · 매각기일)은 우리 자료를 쓴다.
- 거르기: 지분 · 특수 · 자동차(동산) · 입찰가 오기(pro.MISBID 와 같은 기준) · 감정가 없음 · 결과 불분명.
"""

from collections import Counter
from datetime import date

from market import parse_addr_jibun
from usage import classify

KEEP_STATUS = {
    "02",
    "03",
    "04",
}  # 법원 상태: 04·02 = 매각 쪽, 03 = 유찰 쪽 (설계서 3절 대조 결과). 05·01 은 뺌.


def _int(s) -> int | None:
    try:
        return int(float(str(s).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _float(s) -> float | None:
    try:
        v = float(str(s).strip())
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _date8(s) -> date | None:
    s = str(s or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def is_misbid(sale_rate: float | None, win: int | None, min_price: int | None) -> bool:
    """입찰가를 잘못 쓴 것으로 보이는 낙찰: 낙찰가율 300% 이상이고 낙찰가가 최저가의 10배 이상 (pro.MISBID)."""
    return bool(
        sale_rate is not None and sale_rate >= 300 and win and min_price and win >= min_price * 10
    )


def group_instructor(raw: list[dict]) -> tuple[list[dict], int]:
    """강사 원본 행 → 물건 한 줄. 같은 묶음 안에서 금액이 다르면 충돌 수를 센다(0이어야 정상)."""
    groups: dict[tuple, dict] = {}
    conflicts = 0
    for r in raw:
        key = (r["boCd"], r["saNo"], r["maemulSer"], r["maeGiil"])
        if key not in groups:
            groups[key] = dict(r)
            continue
        g = groups[key]
        if (g["gamevalAmt"], g["minmaePrice"], g["maeAmt"]) != (
            r["gamevalAmt"],
            r["minmaePrice"],
            r["maeAmt"],
        ):
            conflicts += 1
        if _float(r.get("maxArea")) and not _float(g.get("maxArea")):
            g["maxArea"] = r["maxArea"]
    return list(groups.values()), conflicts


def code_pairs_instructor(raw: list[dict]) -> list[tuple[str | None, str | None]]:
    """(소분류 코드, 용도 이름) 쌍 — 「기타」 이름을 코드 표로 바꿀 때 쓴다."""
    return [(r.get("sclsUtilCd") or r.get("mclsUtilCd") or None, r.get("dspslUsgNm")) for r in raw]


class Geo:
    """법원 지역 이름 → 시군구 · 시도 코드. 실거래 sgg.json 이 원본.

    「경기도 화성시」처럼 구 없이 쓰인 이름은 법정동이 어느 구에 속하는지(실거래 법정동 목록)로 고른다."""

    ALIAS = {"서울": "서울특별시"}

    def __init__(self, names: dict[str, str], umd_by_sgg: dict[str, set[str]]):
        self.names = names  # 코드 → 이름
        self.inv = {v: k for k, v in names.items()}
        self.umd_by_sgg = umd_by_sgg
        self.sido_of_name = {v.split()[0]: k[:2] for k, v in names.items()}

    def _norm_sido(self, sido: str) -> str:
        return self.ALIAS.get(sido, sido)

    def sgg(self, sido: str, sigu: str, dong: str | None) -> str | None:
        full = f"{self._norm_sido(sido)} {sigu}".strip()
        if full in self.inv:
            return self.inv[full]
        cands = [c for n, c in self.inv.items() if n.startswith(full + " ")]
        if len(cands) == 1:
            return cands[0]
        if dong:
            hits = [c for c in cands if dong in self.umd_by_sgg.get(c, ())]
            if len(hits) == 1:
                return hits[0]
        return None

    def sido_code(self, sido: str) -> str | None:
        return self.sido_of_name.get(self._norm_sido(sido))


def instructor_row(g: dict, geo: Geo, code_map: dict[str, str]) -> dict:
    """묶은 강사 행 → 표준 한 줄. 결과가 불분명하면 result='?'."""
    status, win = g.get("mulStatcd"), _int(g.get("maeAmt")) or 0
    if status in ("02", "04") and win > 0:
        result = "sold"
    elif status == "03" and win == 0:
        result = "failed"
    else:
        result = "?"
    dong = (g.get("hjguDong") or "").strip() or None
    sgg = geo.sgg(g.get("hjguSido") or "", (g.get("hjguSigu") or "").strip(), dong)
    sido = (sgg[:2] if sgg else None) or geo.sido_code(g.get("hjguSido") or "")
    appraisal = _int(g.get("gamevalAmt"))
    min_price = _int(g.get("minmaePrice"))
    sale_rate = round(win * 100 / appraisal, 1) if result == "sold" and appraisal else None
    return {
        "src": "court",
        "court_code": g["boCd"],
        "case_no": g["srnSaNo"],
        "item_no": _int(g["maemulSer"]),
        "sale_date": _date8(g["maeGiil"]),
        "category": classify(
            g.get("dspslUsgNm"), g.get("sclsUtilCd") or g.get("mclsUtilCd"), code_map
        ),
        "usage_raw": g.get("dspslUsgNm"),
        "result": result,
        "failed_count": _int(g.get("yuchalCnt")),
        "appraisal_krw": appraisal,
        "min_price_krw": min_price,
        "winning_bid_krw": win if result == "sold" else None,
        "sale_rate": sale_rate,
        "min_rate": round(min_price * 100 / appraisal, 2) if appraisal and min_price else None,
        "area_m2": _float(g.get("maxArea")) or _float(g.get("minArea")),
        "sido": sido,
        "sgg": sgg,
        "umd": dong,
        "jibun": None,  # 강사 자료에는 지번이 없다(maejibun 은 등기 설명)
        "bldg_name": (g.get("buldNm") or "").strip() or None,
        "is_share": "지분" in (g.get("mulBigo") or ""),
        "is_special": False,  # 강사 자료에는 특수 표시가 없다 — 이 자료에서는 뺄 근거가 없음
        "signal_count": None,
        "high_count": None,
        "tenant_count": None,
    }


def ours_row(r: dict, code_map: dict[str, str]) -> dict:
    """우리 자료(core.sale_results) 한 줄 → 표준 한 줄. 입찰 전 분석 칸은 있으면 채운다."""
    result = "sold" if r.get("result") == "sold" else "failed"
    appraisal = _int(r.get("appraisal_krw"))
    win = _int(r.get("winning_bid_krw")) if result == "sold" else None
    min_price = _int(r.get("min_price_krw"))
    sale_rate = round(win * 100 / appraisal, 1) if win and appraisal else None
    region = str(r.get("region_code") or "")
    umd, jibun = parse_addr_jibun(r.get("address"))
    sale_date = r["sale_date"]
    if not isinstance(sale_date, date):
        sale_date = date.fromisoformat(str(sale_date)[:10])
    return {
        "src": "ours",
        "court_code": r["court_code"],
        "case_no": r["case_no"],
        "item_no": _int(r["item_no"]),
        "sale_date": sale_date,
        "category": classify(r.get("usage_name"), None, code_map),
        "usage_raw": r.get("usage_name"),
        "result": result,
        "failed_count": _int(r.get("failed_count")),
        "appraisal_krw": appraisal,
        "min_price_krw": min_price,
        "winning_bid_krw": win,
        "sale_rate": sale_rate,
        "min_rate": round(min_price * 100 / appraisal, 2) if appraisal and min_price else None,
        "area_m2": _float(r.get("building_area_m2")),
        "sido": region[:2] or None,
        "sgg": region[:5] or None,
        "umd": umd,
        "jibun": jibun,
        "bldg_name": None,
        "is_share": bool(r.get("is_share")),
        "is_special": bool(r.get("is_special_case")),
        "signal_count": _int(r.get("signal_count")),
        "high_count": _int(r.get("high_count")),
        "tenant_count": _int(r.get("tenant_count")),
    }


def item_key(row: dict) -> tuple:
    return (row["court_code"], row["case_no"], row["item_no"], row["sale_date"])


def merge(court: list[dict], ours: list[dict]) -> tuple[list[dict], dict]:
    """겹치는 물건은 우리 자료를 쓴다. 맞춘 · 못 맞춘 건수를 함께 돌려준다."""
    ours_keys = {item_key(r) for r in ours}
    court_keys = {item_key(r) for r in court}
    # 사건번호 모양만 다른 겹침(법원 · 물건번호 · 매각일은 같음)
    ours_loose = {(k[0], k[2], k[3]) for k in ours_keys}
    shape_diff = sum(
        1
        for r in court
        if item_key(r) not in ours_keys
        and (r["court_code"], r["item_no"], r["sale_date"]) in ours_loose
    )
    merged = [r for r in court if item_key(r) not in ours_keys] + ours
    stats = {
        "court_items": len(court_keys),
        "ours_items": len(ours_keys),
        "matched": len(ours_keys & court_keys),
        "court_only": len(court_keys - ours_keys),
        "ours_only": len(ours_keys - court_keys),
        "shape_mismatch_candidates": shape_diff,
    }
    return merged, stats


def apply_filters(rows: list[dict]) -> tuple[list[dict], Counter]:
    """거르기. 어떤 이유로 몇 건 뺐는지 센다."""
    kept: list[dict] = []
    dropped: Counter = Counter()
    for r in rows:
        if r["result"] == "?":
            dropped["결과 불분명"] += 1
        elif r["category"] is None:
            dropped["용도 모름"] += 1
        elif r["category"] == "제외":
            dropped["동산(자동차·중기)"] += 1
        elif r["is_share"]:
            dropped["지분"] += 1
        elif r["is_special"]:
            dropped["특수"] += 1
        elif not r["appraisal_krw"] or r["sale_date"] is None:
            dropped["감정가 · 날짜 없음"] += 1
        elif r["result"] == "sold" and not r["winning_bid_krw"]:
            dropped["낙찰가 없음"] += 1
        elif r["result"] == "sold" and is_misbid(
            r["sale_rate"], r["winning_bid_krw"], r["min_price_krw"]
        ):
            dropped["입찰가 오기"] += 1
        else:
            kept.append(r)
    return kept, dropped
