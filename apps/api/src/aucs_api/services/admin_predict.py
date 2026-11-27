"""관리자 「낙찰가 예측」(11/21 대표님 — 핵심 경쟁력 · 나중에 따로 팔 상품): 쌓인 낙찰 순간 기록으로 그때그때 셈.

- 자료는 analysis.sale_snapshots 뿐 — 입찰일 0시 전에 보여 준 분석(나중에 다시 돈 분석으로 재지 않음).
- 성적표: 상세 성적표(pro._SCORE_SQL)와 같은 조건(유찰 1회 이상 · 처음 나온 물건 · 표본 적음 · 지분 · 특수 · 자동차 ·
  입찰가 오기 뺌)을 달마다.
- 요인표: 주거(아파트 / 빌라) 낙찰, 「낙찰가 ÷ 시세」. 같은 종류 · 같은 유찰 묶음의 가운데 값과의 차이(%p)의 가운데 값.
  기준(claude/요인표.md): 있는 쪽 · 없는 쪽 각 50건 이상 + 최근 석 달 같은 쪽(달마다 5건 이상) → 「통과 후보」.
  셋째 기준(넣었을 때 성적표가 오르는지)은 넣어 봐야 알아 화면에 「확인 필요」.
- 상식과 반대(떠안는 권리 · 지분 · 지하 등이 + 로 나옴)면 「원인부터」 + 그 물건 5건.
- 나눠 보기(score_split): 성적표와 같은 거르기, 종류 × 유찰 묶음(1 · 2 · 3회 이상)으로 쪼갠 성적.
- 그림자 — 시세 기준(shadow_market, 11/28): 같은 낙찰을 「낙찰가 ÷ 시세」 분포로 다시 맞혀 현행과 나란히 견줌
  (화면만 — 손님 예측 · 분석 엔진은 그대로).
"""

import re
from bisect import bisect_left
from collections import defaultdict
from statistics import median
from typing import Any

from aucs_rules.find_filter import VEHICLES

from aucs_api.cache import memo
from aucs_api.db import connect
from aucs_api.services.pro import MISBID

HOUSING = ("아파트", "다세대", "연립주택,다세대,빌라")
MIN_SIDE, MIN_MONTH, MONTHS = 50, 5, 3
# 상식으로는 낙찰가를 낮춰야 하는 요인 — + 로 나오면 원인부터 봄
EXPECT_DOWN = {
    "sig:risk.prior_rights", "sig:risk.lease_reg", "sig:risk.share", "sig:risk.lien",
    "sig:risk.land_right", "sig:risk.illegal", "sig:risk.superficies", "floor:지하",
}  # fmt: skip

_SCORE_SQL = f"""
select to_char(s.sale_date, 'YYYY-MM') as month, count(*)::int as n,
       count(*) filter (where s.sale_rate between p25 and p75)::int as inside,
       count(*) filter (where s.sale_rate < p25)::int as below,
       count(*) filter (where s.sale_rate > p75)::int as above
from (select s.*, (s.analysis -> 'sale_rate' ->> 'p25')::numeric as p25,
             (s.analysis -> 'sale_rate' ->> 'p75')::numeric as p75
      from analysis.sale_snapshots s) s
where s.result = 'sold' and s.sale_rate is not null and not {MISBID}
  and coalesce(s.failed_count, 0) > 0
  and not coalesce(s.is_special_case, false) and not coalesce(s.is_share, false)
  and coalesce(s.usage_name, '') !~ '{VEHICLES}'
  and p25 is not null and p75 is not null
  and not coalesce((s.analysis -> 'sale_rate' ->> 'small_sample')::boolean, false)
  and not coalesce((s.analysis ->> 'new_item')::boolean, false)
group by 1 order by 1
"""

_KEPT_SQL = """
select to_char(sale_date, 'YYYY-MM') as month,
       count(*) filter (where result = 'sold')::int as sold,
       count(*) filter (where result = 'failed')::int as failed,
       count(*) filter (where result = 'sold' and analysis -> 'market' ->> 'price_krw' is not null)::int as sold_market
from analysis.sale_snapshots group by 1 order by 1
"""

_ROWS_SQL = f"""
select s.item_id, s.sale_date, to_char(s.sale_date, 'YYYY-MM') as month,
       case when s.usage_name = '아파트' then 'apt' else 'villa' end as u,
       least(coalesce(s.failed_count, 0), 3) as g,
       s.winning_bid_krw::float / (s.analysis -> 'market' ->> 'price_krw')::bigint * 100 as ratio,
       s.analysis -> 'signals' as signals, s.analysis -> 'building' as b, i.address
from analysis.sale_snapshots s left join core.items i using (item_id)
where s.result = 'sold' and s.winning_bid_krw > 0 and s.usage_name = any(%s) and not {MISBID}
  and (s.analysis -> 'market' ->> 'price_krw')::bigint > 0
"""


# 줄 단위 하나로 받아 나눠 보기 · 그림자가 같이 씀(서버 호출을 늘리지 않음). 거르기 = 지분 · 특수 · 자동차 · 입찰가 오기 뺌.
# 성적표 대상(유찰 1회 이상 · 처음 나온 물건 · 표본 적음 뺌)인지는 파이썬에서 가림 — 그림자 풀은 더 넓게(유찰 0 포함).
_SPLIT_SQL = f"""
select s.sale_date, s.usage_name, coalesce(s.failed_count, 0) as failed_count,
       s.sale_rate::float as sale_rate, (s.analysis -> 'sale_rate' ->> 'p25')::float as p25,
       (s.analysis -> 'sale_rate' ->> 'p50')::float as p50, (s.analysis -> 'sale_rate' ->> 'p75')::float as p75,
       coalesce((s.analysis -> 'sale_rate' ->> 'small_sample')::boolean, false) as small_sample,
       coalesce((s.analysis ->> 'new_item')::boolean, false) as new_item,
       s.appraisal_krw, s.min_price_krw, s.winning_bid_krw,
       (s.analysis -> 'market' ->> 'price_krw')::bigint as market_krw, i.address
from analysis.sale_snapshots s left join core.items i using (item_id)
where s.result = 'sold' and s.winning_bid_krw > 0 and not {MISBID}
  and not coalesce(s.is_special_case, false) and not coalesce(s.is_share, false)
  and coalesce(s.usage_name, '') !~ '{VEHICLES}'
"""

KINDS = ("아파트", "빌라", "오피스텔", "상가", "땅", "그 밖")
VILLA = ("다세대", "연립주택,다세대,빌라", "연립주택")
_SHOP = re.compile(r"근린|상가|판매")
_LAND = re.compile(r"전답|임야|대지|잡종지|과수원|목장|공장용지|구거|유지|묘지|도로|^[전답]$")
MIN_CELL = 15  # 나눠 보기 칸이 이보다 적으면 「표본 적음」
MIN_POOL = 30  # 그림자 비교 사례(같은 종류 · 유찰 묶음)가 이보다 적으면 시도 → 전국 → 제외
POOL_DAYS = 365


def kind_of(usage: str | None) -> str:
    """법원 용도 이름 → 종류."""
    u = usage or ""
    if u == "아파트":
        return "아파트"
    if u in VILLA:
        return "빌라"
    if u == "오피스텔":
        return "오피스텔"
    if _SHOP.search(u):
        return "상가"
    if _LAND.search(u):
        return "땅"
    return "그 밖"


def fail_bucket(n: int | None) -> int:
    """유찰 묶음: 0 · 1 · 2 · 3회 이상."""
    return min(max(n or 0, 0), 3)


def is_scored(r: dict[str, Any]) -> bool:
    """성적표(_SCORE_SQL)와 같은 대상: 유찰 1회 이상 · 낙찰가율 · p25~p75 있음 · 표본 적음 · 처음 나온 물건 아님."""
    return bool(
        fail_bucket(r["failed_count"]) > 0
        and r["sale_rate"] is not None
        and r["p25"] is not None
        and r["p50"] is not None
        and r["p75"] is not None
        and not r["small_sample"]
        and not r["new_item"]
        and r["appraisal_krw"]
    )


def _current(r: dict[str, Any]) -> dict[str, float]:
    """현행 예측: lo · hi 는 낙찰가율(%) p25 · p75, mid 는 감정가 × p50 ÷ 100(원, 오차용)."""
    return {
        "lo": float(r["p25"]),
        "mid": float(r["appraisal_krw"]) * float(r["p50"]) / 100,
        "hi": float(r["p75"]),
        "rate": float(r["sale_rate"]),
        "win": float(r["winning_bid_krw"]),
    }


def _cell(items: list[dict[str, float]]) -> dict[str, Any]:
    """칸 하나의 성적. 가운데 오차 = |낙찰가 − 예상 가운데| ÷ 낙찰가 의 가운데 값(%)."""
    n = len(items)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "inside": round(100 * sum(1 for i in items if i["lo"] <= i["rate"] <= i["hi"]) / n, 1),
        "below": round(100 * sum(1 for i in items if i["rate"] < i["lo"]) / n, 1),
        "above": round(100 * sum(1 for i in items if i["rate"] > i["hi"]) / n, 1),
        "mid_err": round(100 * median(abs(i["win"] - i["mid"]) / i["win"] for i in items), 1),
    }


def score_split(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """나눠 보기(순수 함수): 종류 × 유찰 묶음(1 · 2 · 3회 이상)의 성적. 15건 미만 칸은 few=True 로 건수만."""
    cells: dict[tuple[str, int], list[dict[str, float]]] = defaultdict(list)
    for r in rows:
        if is_scored(r):
            cells[(kind_of(r["usage_name"]), fail_bucket(r["failed_count"]))].append(_current(r))
    out = []
    for kind in KINDS:
        for g in (1, 2, 3):
            items = cells.get((kind, g), [])
            if not items:
                continue
            c = _cell(items)
            out.append(
                {
                    "kind": kind,
                    "g": g,
                    **({"n": c["n"], "few": True} if c["n"] < MIN_CELL else {**c, "few": False}),
                }
            )
    return out


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _sido(address: str | None) -> str | None:
    parts = (address or "").split()
    return parts[0] if parts else None


def shadow_market(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """그림자 — 시세 기준(순수 함수, DB · 현재 시각 안 씀). 같은 낙찰을 「낙찰가 ÷ 시세」 분포로 다시 맞혀 현행과 견줌.

    대상: 성적표와 같은 조건 + 시세 > 0. 비교 사례: 대상 입찰일 앞선 365일 안(당일 · 뒤는 절대 안 넣음) 낙찰 중
    같은 종류 · 같은 유찰 묶음 · 시세 > 0, 같은 시도 30건 이상이면 그것, 아니면 전국 30건 이상, 그래도 모자라면 「제외」.
    범위 = 시세 × ratio 의 25 · 50 · 75% 지점, 셋 다 최저가 밑으로 안 감. 감정가 비율로 바꿔 낙찰가율과 견줌."""
    pool: dict[tuple[str, int], list[tuple[Any, float, str | None]]] = defaultdict(list)
    for r in rows:
        if r["market_krw"] and r["market_krw"] > 0 and r["winning_bid_krw"]:
            pool[(kind_of(r["usage_name"]), fail_bucket(r["failed_count"]))].append(
                (
                    r["sale_date"],
                    float(r["winning_bid_krw"]) / float(r["market_krw"]),
                    _sido(r["address"]),
                )
            )
    dates: dict[tuple[str, int], list[Any]] = {}
    for k, v in pool.items():
        v.sort(key=lambda x: x[0])
        dates[k] = [x[0] for x in v]
    acc: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"cur": [], "sh": [], "excluded": 0}
    )
    for r in rows:
        if not is_scored(r) or not r["market_krw"] or r["market_krw"] <= 0:
            continue
        kind, g = kind_of(r["usage_name"]), fail_bucket(r["failed_count"])
        d = r["sale_date"]
        keys = [(d.strftime("%Y-%m"), kind), (d.strftime("%Y-%m"), "전체")]
        lst, ds = pool.get((kind, g), []), dates.get((kind, g), [])
        lo_i = bisect_left(ds, d.fromordinal(d.toordinal() - POOL_DAYS))
        hi_i = bisect_left(ds, d)  # 입찰일 당일 · 뒤는 안 들어감
        window = lst[lo_i:hi_i]
        sido = _sido(r["address"])
        ratios = [x[1] for x in window if sido and x[2] == sido]
        if len(ratios) < MIN_POOL:
            ratios = [x[1] for x in window]
        if len(ratios) < MIN_POOL:
            for k in keys:
                acc[k]["excluded"] += 1
            continue
        mkt, app = float(r["market_krw"]), float(r["appraisal_krw"])
        floor = float(r["min_price_krw"]) if r["min_price_krw"] else 0.0
        lo, mid, hi = (max(_quantile(ratios, q) * mkt, floor) for q in (0.25, 0.5, 0.75))
        cur = _current(r)
        sh = {
            "lo": lo / app * 100,
            "mid": mid,
            "hi": hi / app * 100,
            "rate": cur["rate"],
            "win": cur["win"],
        }
        for k in keys:
            acc[k]["cur"].append(cur)
            acc[k]["sh"].append(sh)
    out = [
        {
            "month": m,
            "kind": k,
            "excluded": a["excluded"],
            "current": _cell(a["cur"]),
            "shadow": _cell(a["sh"]),
        }
        for (m, k), a in sorted(acc.items())
    ]
    return {"rows": out, "pool_min": MIN_POOL, "pool_days": POOL_DAYS}


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def factor_keys(r: dict[str, Any]) -> list[tuple[str, str]]:
    """낙찰 한 건 → (요인 키, 이름) 목록(순수 함수)."""
    out = [(f"fail:{r['g']}", f"유찰 {r['g']}회" + (" 이상" if r["g"] == 3 else ""))]
    seen: set[str] = set()
    for e in r["signals"] if isinstance(r["signals"], list) else []:
        rid = (e or {}).get("rule_id")
        if rid and rid not in seen:
            seen.add(rid)
            out.append((f"sig:{rid}", (e.get("title") or rid).split(" — ")[0]))
    b = r["b"] if isinstance(r["b"], dict) else {}
    age, fl, top, units = (_int(b.get(k)) for k in ("age_years", "unit_floor", "floors_above", "complex_units"))  # fmt: skip
    if age is not None:
        band = "0~9" if age < 10 else "10~19" if age < 20 else "20~29" if age < 30 else "30+"
        out.append((f"age:{band}", f"사용승인 {band}년"))
    if fl is not None and top is not None:
        f = "지하" if fl < 1 else "1층" if fl == 1 else "꼭대기층" if fl == top else "중간층"
        out.append((f"floor:{f.replace('층', '') if f != '1층' else f}", f))
    if units is not None:
        band = (
            "~19"
            if units < 20
            else "20~99"
            if units < 100
            else "100~499"
            if units < 500
            else "500+"
        )
        out.append((f"units:{band}", f"단지 {band}세대"))
    return out


def factor_table(rows: list[dict[str, Any]], months: list[str]) -> list[dict[str, Any]]:
    """요인마다 효과 · 달마다 효과 · 기준 통과(순수 함수). rows: u · g · ratio · month · 요인."""
    base: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in rows:
        base[(r["u"], r["g"])].append(r["ratio"])
    gmed = {k: median(v) for k, v in base.items()}
    total = defaultdict(int)
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        total[r["u"]] += 1
        dev = r["ratio"] - gmed[(r["u"], r["g"])]
        for key, name in factor_keys(r):
            a = acc.setdefault(
                (r["u"], key),
                {"name": name, "dev": [], "ratio": [], "by": defaultdict(list), "ex": []},
            )
            a["dev"].append(dev)
            a["ratio"].append(r["ratio"])
            a["by"][r["month"]].append(dev)
            a["ex"].append((dev, r))
    last = months[-MONTHS:]
    out = []
    for (u, key), a in acc.items():
        n = len(a["dev"])
        if n < 15:
            continue
        eff = round(median(a["dev"]), 1)
        by = {
            m: (round(median(a["by"][m]), 1) if len(a["by"][m]) >= MIN_MONTH else None)
            for m in last
        }
        steady = len(last) == MONTHS and all(v is not None and v != 0 and (v > 0) == (eff > 0) for v in by.values())  # fmt: skip
        wrong = key in EXPECT_DOWN and eff > 0
        ex = sorted(a["ex"], key=lambda x: -x[0])[:5] if wrong else []
        out.append({
            "u": u, "key": key, "name": a["name"], "n": n, "n_without": total[u] - n,
            "effect": eff, "ratio": round(median(a["ratio"]), 1), "by_month": by,
            "enough": n >= MIN_SIDE and total[u] - n >= MIN_SIDE, "steady": steady,
            "wrong_way": wrong,
            "examples": [{"item_id": r["item_id"], "address": r["address"], "sale_date": r["sale_date"].isoformat(),
                          "ratio": round(r["ratio"], 1)} for _, r in ex],
        })  # fmt: skip
    order = {"fail": 0, "floor": 1, "age": 2, "units": 3, "sig": 4}
    return sorted(out, key=lambda x: (x["u"], order.get(x["key"].split(":")[0], 9), -x["n"]))


@memo(ttl=3600, size=2)
def screen() -> dict[str, Any]:
    with connect() as c:
        kept = c.execute(_KEPT_SQL).fetchall()
        score = c.execute(_SCORE_SQL).fetchall()
        rows = c.execute(_ROWS_SQL, (list(HOUSING),)).fetchall()
        split_rows = c.execute(_SPLIT_SQL).fetchall()
    months = sorted({r["month"] for r in rows})
    counts = defaultdict(int)
    for r in rows:
        counts[r["u"]] += 1
    return {
        "kept": kept,
        "score": score,
        "months": months[-MONTHS:],
        "sample": dict(counts),
        "rule": {"min_side": MIN_SIDE, "min_month": MIN_MONTH, "months": MONTHS},
        "factors": factor_table(rows, months),
        "score_split": score_split(split_rows),
        "shadow_market": shadow_market(split_rows),
    }
