"""학습 표 만들기 (순수 함수): 강사 법원 자료 · 우리 자료를 한 줄(낙찰 · 유찰 한 건)씩 모은다.

- 강사 자료: 한 물건이 토지 · 건물 여러 줄 → (boCd, saNo, maemulSer, maeGiil) 로 한 줄. 매각 = 낙찰가 > 0.
- 우리 자료: core.sale_results. 겹치는 물건(같은 법원 · 사건 · 물건번호 · 매각기일)은 우리 자료를 쓴다.
- 거르기: 지분 · 특수 · 자동차(동산) · 입찰가 오기(pro.MISBID 와 같은 기준) · 감정가 없음 · 결과 불분명.
"""

import math
import re
from collections import Counter, defaultdict
from datetime import date

from aucs_rules.sale_rate import effective_failed
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


def implied_rounds(
    court: str | None,
    appraisal: int | None,
    min_price: int | None,
    failed: int | None,
    pct: dict[str, float],
) -> int | None:
    """최저가로 센 유찰 횟수 — DB 의 core.price_round(0077)와 같은 셈.
    최저가 ≥ 감정가 → 0. 아니면 ln(최저가÷감정가) ÷ ln(1−법원 저감률)이 정수(±0.15)이고 법원 숫자보다 작을 때만 그 값. 못 세면 None."""
    if not appraisal or not min_price or appraisal <= 0 or min_price <= 0:
        return None
    if min_price >= appraisal:
        return 0
    p = pct.get(court or "")
    if p is None or not 0 < p < 100:
        return None
    s = math.log(min_price / appraisal) / math.log(1 - p / 100)
    if abs(s - round(s)) < 0.15 and (failed is None or round(s) < failed):
        return int(round(s))
    return None


def prior_date_counts(grouped: list[dict]) -> dict[tuple, int]:
    """강사 자료: 같은 물건(법원 · 사건 · 물건번호)의 「이전 매각기일 줄 수」. 키 (boCd, saNo, maemulSer, maeGiil) → 개수.
    강사 자료는 17주치뿐이라 그 전 기일은 셀 수 없다(모자랄 수는 있어도 넘칠 수는 거의 없음)."""
    dates: dict[tuple, list[str]] = defaultdict(list)
    for g in grouped:
        dates[(g["boCd"], g["saNo"], g["maemulSer"])].append(str(g["maeGiil"]))
    out: dict[tuple, int] = {}
    for (bo, sa, ser), ds in dates.items():
        ds_sorted = sorted(set(ds))
        for d in ds_sorted:
            out[(bo, sa, ser, d)] = sum(1 for x in ds_sorted if x < d)
    return out


ROUND_CANDIDATES = ("yuchal", "yuchal-1", "prior")


def candidate_rounds(name: str, yuchal: int | None, prior: int | None) -> int:
    """후보 값: 법원 숫자(yuchalCnt) · 법원 숫자 − 1 · 같은 물건의 앞 기일 수."""
    if name == "prior":
        return prior or 0
    y = yuchal or 0
    return max(y - 1, 0) if name == "yuchal-1" else y


def choose_fallback(samples: list[tuple]) -> tuple[str, dict[str, float]]:
    """최저가로 센 값을 낼 수 있는 물건들(samples: (implied, yuchal, prior))에서 후보마다 맞은 비율을 재서
    가장 많이 맞는 후보를 고른다. 최저가로 못 세는 물건에는 그 후보를 쓴다. 돌려주는 값: (후보 이름, 후보별 맞은 비율)."""
    if not samples:
        return "yuchal", {}
    rate = {
        c: sum(1 for imp, y, p in samples if candidate_rounds(c, y, p) == imp) / len(samples)
        for c in ROUND_CANDIDATES
    }
    return max(ROUND_CANDIDATES, key=lambda c: (rate[c], c == "yuchal")), rate


def pick_rounds(
    court: str | None,
    appraisal: int | None,
    min_price: int | None,
    yuchal: int | None,
    prior: int | None,
    pct: dict[str, float],
    fallback: str = "yuchal",
) -> tuple[int, str]:
    """강사 자료 유찰 횟수 정하기. 돌려주는 값: (횟수, 어떻게 정했나).
    ① 최저가로 센 값(DB 의 price_round 와 같은 셈)이 있으면 그것.
    ② 못 세면(저감률 모르는 법원 · 정수 아님) fallback 후보 — 법원 숫자 · 법원 숫자−1 · 앞 기일 수 중 ①과 가장 잘 맞은 쪽(choose_fallback)."""
    imp = implied_rounds(court, appraisal, min_price, yuchal, pct)
    if imp is not None:
        return imp, "최저가로 셈"
    return candidate_rounds(fallback, yuchal, prior), f"최저가로 못 셈 → {fallback}"


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


def _num(s) -> float | None:
    try:
        v = float(str(s).strip())
        return v if v != 0 else None
    except (TypeError, ValueError):
        return None


_PAREN_DONG = re.compile(r"\(([가-힣0-9]+(?:동|가|리))")


def rate_sigungu(sigungu_txt: str | None, address: str | None = None) -> str | None:
    """① 비교 사례를 묶는 시군구 글 — 운영과 같게 「시」 단위: 경기 「수원시 권선구」→ 수원시, 서울 「강남구」→ 강남구.
    글 칸이 없으면 주소 둘째 낱말(analyze.sigungu_from_address 와 같음)."""
    if sigungu_txt and sigungu_txt.strip():
        return sigungu_txt.split()[0]
    parts = (address or "").split()
    if len(parts) > 1 and parts[1][-1:] in ("시", "군", "구"):
        return parts[1]
    return None


def region_from_address(
    geo: "Geo", address: str | None, sido_name: str | None
) -> tuple[str | None, str | None]:
    """우리 자료의 주소 글로 (시군구 코드, 시도 코드). 운영 analyze 는 sale_results.sido 글 · items.sigungu(없으면 주소에서)로
    비교 사례를 묶는다 — region_code 는 12% 가 비어 있고 틀린 것도 있어 그 칸만 믿으면 묶음이 달라진다."""
    sido = geo.sido_code(sido_name or "") if sido_name else None
    parts = (address or "").split()
    if len(parts) < 2:
        return None, sido
    sido = geo.sido_code(parts[0]) or sido
    sigu = parts[1]
    if len(parts) > 2 and parts[1].endswith("시") and parts[2].endswith("구"):
        sigu = f"{parts[1]} {parts[2]}"
    m = _PAREN_DONG.search(address or "")
    dong = m.group(1) if m else parse_addr_jibun(address)[0]
    sgg = geo.sgg(parts[0], sigu, dong)
    return sgg, (sgg[:2] if sgg else sido)


def instructor_row(
    g: dict,
    geo: Geo,
    code_map: dict[str, str],
    pct: dict[str, float] | None = None,
    prior: dict[tuple, int] | None = None,
    fallback: str = "yuchal",
) -> dict:
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
    yuchal = _int(g.get("yuchalCnt"))
    prior_n = (prior or {}).get((g["boCd"], g["saNo"], g["maemulSer"], str(g["maeGiil"])))
    eff, eff_how = pick_rounds(
        g["boCd"], appraisal, min_price, yuchal, prior_n, pct or {}, fallback
    )
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
        "failed_count": yuchal,
        "prior_dates": prior_n,
        "eff_failed": eff,
        "eff_how": eff_how,
        "price_round": None,
        "appraisal_krw": appraisal,
        "min_price_krw": min_price,
        "winning_bid_krw": win if result == "sold" else None,
        "sale_rate": sale_rate,
        "min_rate": round(min_price * 100 / appraisal, 2) if appraisal and min_price else None,
        "area_m2": _float(g.get("maxArea")) or _float(g.get("minArea")),
        "sido": sido,
        "sgg": sgg,
        "sigungu_txt": (g.get("hjguSigu") or "").strip() or None,
        "rate_sigungu": rate_sigungu(g.get("hjguSigu")),
        "umd": dong,
        "jibun": None,  # 강사 자료에는 지번 칸이 없다 — 시세 붙일 때 market.find_jibun 이 (a)~(d)로 찾음
        "maejibun": (g.get("maejibun") or "").strip() or None,
        "kx": _num(g.get("xCordi")),  # KATEC(TM128) 미터. wgs84 칸은 정수 도(127 · 37)뿐이라 못 씀
        "ky": _num(g.get("yCordi")),
        "bldg_name": (g.get("buldNm") or "").strip() or None,
        "is_share": "지분" in (g.get("mulBigo") or ""),
        "is_special": False,  # 강사 자료에는 특수 표시가 없다 — 이 자료에서는 뺄 근거가 없음
        "signal_count": None,
        "high_count": None,
        "tenant_count": None,
        "snap_p25": None,
        "snap_p50": None,
        "snap_p75": None,
        "snap_n": None,
        "snap_scope": None,
        "snap_date": None,
        "snap_engine": None,
    }


def ours_row(r: dict, code_map: dict[str, str], geo: "Geo | None" = None) -> dict:
    """우리 자료(core.sale_results) 한 줄 → 표준 한 줄. 입찰 전 분석 칸은 있으면 채운다."""
    result = "sold" if r.get("result") == "sold" else "failed"
    appraisal = _int(r.get("appraisal_krw"))
    win = _int(r.get("winning_bid_krw")) if result == "sold" else None
    min_price = _int(r.get("min_price_krw"))
    sale_rate = round(win * 100 / appraisal, 1) if win and appraisal else None
    region = str(r.get("region_code") or "")
    umd, jibun = parse_addr_jibun(r.get("address"))
    sgg, sido = region[:5] or None, region[:2] or None
    if geo is not None:
        a_sgg, a_sido = region_from_address(geo, r.get("address"), r.get("sido_name"))
        sgg, sido = a_sgg or sgg, a_sido or sido
    sale_date = r["sale_date"]
    if not isinstance(sale_date, date):
        sale_date = date.fromisoformat(str(sale_date)[:10])
    failed = _int(r.get("failed_count"))
    price_round = _int(r.get("price_round"))
    snap_date = r.get("snap_date")
    if snap_date is not None and not isinstance(snap_date, date):
        snap_date = date.fromisoformat(str(snap_date)[:10])
    return {
        "src": "ours",
        "court_code": r["court_code"],
        "case_no": r["case_no"],
        "item_no": _int(r["item_no"]),
        "sale_date": sale_date,
        "category": classify(r.get("usage_name"), None, code_map),
        "usage_raw": r.get("usage_name"),
        "result": result,
        "failed_count": failed,
        "prior_dates": None,
        "eff_failed": effective_failed(failed, appraisal, min_price, price_round),
        "eff_how": "price_round",
        "price_round": price_round,
        "appraisal_krw": appraisal,
        "min_price_krw": min_price,
        "winning_bid_krw": win,
        "sale_rate": sale_rate,
        "min_rate": round(min_price * 100 / appraisal, 2) if appraisal and min_price else None,
        "area_m2": _float(r.get("building_area_m2")),
        "sido": sido,
        "sgg": sgg,
        "sigungu_txt": (r.get("sigungu_txt") or "").strip() or None,
        "rate_sigungu": rate_sigungu(r.get("sigungu_txt"), r.get("address")),
        "umd": umd,
        "jibun": jibun,
        "maejibun": None,
        "kx": None,
        "ky": None,
        "bldg_name": None,
        "is_share": bool(r.get("is_share")),
        "is_special": bool(r.get("is_special_case")),
        "signal_count": _int(r.get("signal_count")),
        "high_count": _int(r.get("high_count")),
        "tenant_count": _int(r.get("tenant_count")),
        "snap_p25": _float_or_none(r.get("snap_p25")),
        "snap_p50": _float_or_none(r.get("snap_p50")),
        "snap_p75": _float_or_none(r.get("snap_p75")),
        "snap_n": _int(r.get("snap_n")),
        "snap_scope": r.get("snap_scope"),
        "snap_date": snap_date,
        "snap_engine": r.get("snap_engine"),
    }


def _float_or_none(v) -> float | None:
    try:
        return None if v is None or v != v else float(v)
    except (TypeError, ValueError):
        return None


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
