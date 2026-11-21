"""관리자 「낙찰가 예측」(11/21 대표님 — 핵심 경쟁력 · 나중에 따로 팔 상품): 쌓인 낙찰 순간 기록으로 그때그때 셈.

- 자료는 analysis.sale_snapshots 뿐 — 입찰일 0시 전에 보여 준 분석(나중에 다시 돈 분석으로 재지 않음).
- 성적표: 상세 성적표(pro._SCORE_SQL)와 같은 조건(유찰 1회 이상 · 처음 나온 물건 · 표본 적음 · 지분 · 특수 · 자동차 ·
  입찰가 오기 뺌)을 달마다.
- 요인표: 주거(아파트 / 빌라) 낙찰, 「낙찰가 ÷ 시세」. 같은 종류 · 같은 유찰 묶음의 가운데 값과의 차이(%p)의 가운데 값.
  기준(claude/요인표.md): 있는 쪽 · 없는 쪽 각 50건 이상 + 최근 석 달 같은 쪽(달마다 5건 이상) → 「통과 후보」.
  셋째 기준(넣었을 때 성적표가 오르는지)은 넣어 봐야 알아 화면에 「확인 필요」.
- 상식과 반대(떠안는 권리 · 지분 · 지하 등이 + 로 나옴)면 「원인부터」 + 그 물건 5건.
"""

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
    }
