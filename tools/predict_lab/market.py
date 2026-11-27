"""당시 시세: 국토부 실거래를 입찰일 전 자료만으로 붙인다(aucs_rules.price.market_price 를 그대로 부름).

- 종류: 아파트(apt_sale) · 빌라(rowhouse_sale) · 오피스텔(officetel_sale)만. 그 밖은 시세 없음.
- 같은 물건 찾기: 시군구 + 법정동 + 지번(우리 자료는 주소에서 지번을 읽음).
  강사 법원 자료에는 지번이 없어(maejibun 은 등기 설명) 단지 이름(buldNm)으로 대신한다[내 판단].
- 기준일 = 매각일 - 1일. 매각일 당일 · 뒤 거래는 쓰지 않음.
"""

import gzip
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from aucs_rules.price import Trade, market_price
from aucs_rules.result import RuleResult
from paths import REALTRADE_DIR

REAL_KIND = {"아파트": "apt_sale", "빌라": "rowhouse_sale", "오피스텔": "officetel_sale"}
NAME_FIELD = {"아파트": "aptNm", "빌라": "mhouseNm", "오피스텔": "offiNm"}

# 주소에서 법정동 + 지번: 「경기도 안산시 상록구 부곡동 647-15 제이앤빌 3층302호」 → (부곡동, 647-15)
_ADDR_JIBUN = re.compile(r"([가-힣0-9]+(?:동|가|리))\s+(\d+(?:-\d+)?)")


def parse_addr_jibun(address: str | None) -> tuple[str | None, str | None]:
    """주소 문자열에서 (법정동, 지번). 못 찾으면 (None, None)."""
    if not address:
        return None, None
    m = _ADDR_JIBUN.search(address)
    return (m.group(1), m.group(2)) if m else (None, None)


def norm_name(name: str | None) -> str:
    """단지 이름 비교용: 공백 · 괄호 · 하이픈을 떼고 소문자로."""
    return re.sub(r"[\s()\-]", "", name or "").lower()


def jibun_key(umd: str, jibun: str) -> str:
    return f"{umd} {jibun}"


def name_key(umd: str, name: str) -> str:
    return f"{umd}|{norm_name(name)}"


def _to_int(s: str | None) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def parse_trade(rec: dict, kind: str) -> tuple[str, str, str | None, Trade, str | None] | None:
    """실거래 한 줄 → (sggCd, 법정동, 지번, 거래, 단지 이름). 필요한 칸이 없으면 None."""
    try:
        d = date(int(rec["dealYear"]), int(rec["dealMonth"]), int(rec["dealDay"]))
        price = int(str(rec["dealAmount"]).replace(",", "").strip()) * 10_000
        area = float(rec["excluUseAr"])
    except (KeyError, TypeError, ValueError):
        return None
    if price <= 0 or area <= 0:
        return None
    name = rec.get(NAME_FIELD[kind]) or None
    cancelled = (rec.get("cdealType") == "O") or bool(rec.get("cdealDay"))
    umd = (rec.get("umdNm") or "").strip()
    jibun = (rec.get("jibun") or "").strip() or None
    trade = Trade(
        deal_date=d,
        price_krw=price,
        area_m2=area,
        floor=_to_int(rec.get("floor")),
        complex_name=None,  # 키는 인덱스 만들 때 정함
        build_year=_to_int(rec.get("buildYear")),
        cancelled=cancelled,
    )
    return str(rec.get("sggCd") or ""), umd, jibun, trade, name


def load_trade_index(
    sgg_codes: set[str], years: range, kinds: tuple[str, ...] = tuple(REAL_KIND)
) -> dict[tuple[str, str], list[Trade]]:
    """(시군구 코드, 비교 키) → 거래 목록. 키는 지번 키와 단지 이름 키 두 가지로 넣는다."""
    index: dict[tuple[str, str], list[Trade]] = defaultdict(list)
    for kind in kinds:
        folder = REALTRADE_DIR / REAL_KIND[kind]
        for y in years:
            for sgg in sgg_codes:
                path = folder / str(y) / f"{sgg}.jsonl.gz"
                if not path.exists():
                    continue
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        parsed = parse_trade(json.loads(line), kind)
                        if parsed is None:
                            continue
                        sgg_cd, umd, jibun, t, name = parsed
                        if not umd:
                            continue
                        if jibun:
                            index[(sgg, jibun_key(umd, jibun))].append(
                                _rekey(t, jibun_key(umd, jibun))
                            )
                        if name:
                            index[(sgg, name_key(umd, name))].append(_rekey(t, name_key(umd, name)))
    return index


def umd_by_sgg(
    sgg_codes: set[str], years: range, kinds: tuple[str, ...] = tuple(REAL_KIND)
) -> dict[str, set[str]]:
    """시군구 코드 → 그 안의 법정동 이름들(실거래 기준). 법원 이름에 구가 빠졌을 때 법정동으로 고른다."""
    out: dict[str, set[str]] = defaultdict(set)
    for kind in kinds:
        for y in years:
            for sgg in sgg_codes:
                path = REALTRADE_DIR / REAL_KIND[kind] / str(y) / f"{sgg}.jsonl.gz"
                if not path.exists():
                    continue
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    for line in f:
                        umd = (json.loads(line).get("umdNm") or "").strip() if line.strip() else ""
                        if umd:
                            out[sgg].add(umd)
    return dict(out)


def _rekey(t: Trade, key: str) -> Trade:
    return Trade(
        deal_date=t.deal_date,
        price_krw=t.price_krw,
        area_m2=t.area_m2,
        floor=t.floor,
        complex_name=key,
        build_year=t.build_year,
        cancelled=t.cancelled,
    )


@dataclass(frozen=True)
class MarketPrice:
    price_krw: int
    level: int
    n: int


def market_for(
    index: dict[tuple[str, str], list[Trade]],
    *,
    category: str,
    sgg: str | None,
    umd: str | None,
    jibun: str | None,
    bldg_name: str | None,
    area_m2: float | None,
    sale_date: date,
) -> MarketPrice | None:
    """한 물건의 당시 시세. 못 붙이면 None(빈칸으로 두고 보고서에 센다)."""
    if category not in REAL_KIND or not sgg or not umd or not area_m2:
        return None
    if jibun:
        key = jibun_key(umd, jibun)
    elif bldg_name:
        key = name_key(umd, bldg_name)
    else:
        return None
    trades = index.get((sgg, key), [])
    if not trades:
        return None
    res: RuleResult = market_price(
        trades, as_of=sale_date - timedelta(days=1), complex_name=key, area_m2=area_m2
    )
    if res.value is None:
        return None
    v = res.value
    return MarketPrice(price_krw=v["price_krw"], level=v["level"], n=v["n"])
