"""등기부 + 임차인 → 예상 배당과 낙찰자가 떠안는 보증금 (순수 함수, 결과는 늘 「추정」).

배당 순서는 distribution.distribute 그대로:
경매비용 → 소액임차인 최우선변제 → (당해세: 금액 몰라 뺌) → 날짜 순(근저당·전세권·담보가등기·확정일자 임차인)
→ 가압류 안분. 근저당은 채권최고액으로 넣어 실제보다 많이 받는 쪽으로 잡습니다
= 임차인 몫이 적게 나와 떠안는 돈을 넉넉히 잡는 쪽(안전한 쪽).
개발 기준이며 3단계 법률 검토 대상입니다.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from aucs_rules.distribution import Claim, distribute
from aucs_rules.fix_dictionary import kind_of, normalize_purpose
from aucs_rules.rights import Right
from aucs_rules.tenants import (
    Tenant,
    assumed_amount,
    claimed_in_time,
    opposing_power,
    priority_date,
    small_lease_amount,
)

COST_MIN_KRW = 2_000_000  # 경매비용(감정료·수수료·송달료 등) 대략
COST_RATE = 0.003
_SECURITY = {"mortgage", "security_provisional_registration", "jeonse"}
_DATED = {"mortgage", "security_provisional_registration", "jeonse"}


@dataclass(frozen=True)
class NamedTenant:
    name: str
    tenant: Tenant


def _short(r: Right) -> str:
    name = normalize_purpose(r.purpose) or r.purpose
    name = name.replace("권설정", "").replace("설정", "")
    return f"{name} · {r.holder}" if r.holder else name


def payout(
    sale_price_krw: int,
    rights: list[Right],
    tenants: list[NamedTenant],
    base_date: date | None,
    claim_deadline: date | None,
    region_class: str | None,
    small_table: list[dict[str, Any]],
) -> dict[str, Any]:
    """예상 배당표와 임차인별 받는 돈·떠안는 돈."""
    dated = [r.receipt_date for r in rights if kind_of(r.purpose) in _SECURITY and r.receipt_date]
    first_security = min(dated) if dated else None
    starts = [
        r.receipt_date for r in rights if kind_of(r.purpose) == "auction_start" and r.receipt_date
    ]
    auction_start = min(starts) if starts else None

    claims: list[Claim] = []
    labels: dict[str, str] = {}
    cost = max(COST_MIN_KRW, int(sale_price_krw * COST_RATE))
    claims.append(Claim("cost", "cost", cost))
    labels["cost"] = "경매비용(대략)"

    t_info = []
    for i, nt in enumerate(tenants):
        t = nt.tenant
        claimed = claimed_in_time(t, claim_deadline).value
        small = 0
        if claimed and t.deposit_krw and region_class:
            small = (
                small_lease_amount(
                    t, region_class, first_security, auction_start, sale_price_krw, small_table
                ).value
                or 0
            )
        if small:
            claims.append(Claim(f"t{i}:small", "top_priority", small))
            labels[f"t{i}:small"] = f"소액임차인 최우선 · {nt.name}"
        prio = priority_date(t).value
        if claimed and t.deposit_krw and prio and t.deposit_krw > small:
            claims.append(Claim(f"t{i}:dated", "dated", t.deposit_krw - small, prio))
            labels[f"t{i}:dated"] = f"확정일자 임차인 · {nt.name}"
        t_info.append((i, nt, claimed))

    unknown = []
    for j, r in enumerate(rights):
        k = kind_of(r.purpose)
        key = f"r{j}"
        if k in _DATED:
            if r.amount_krw is None:
                unknown.append(_short(r))
                continue
            claims.append(Claim(key, "dated", r.amount_krw, r.receipt_date))
        elif k == "provisional_seizure":
            if r.amount_krw is None:
                unknown.append(_short(r))
                continue
            claims.append(Claim(key, "general", r.amount_krw))
        elif k == "seizure":
            unknown.append(_short(r))  # 세금 압류: 금액이 등기부에 없음
            continue
        else:
            continue
        labels[key] = _short(r)

    res = distribute(sale_price_krw, claims)
    paid = res.value["paid"] if res.value else {}
    rows = [
        {"name": labels[c.name], "claim_krw": c.amount_krw, "paid_krw": paid.get(c.name, 0)}
        for c in sorted(claims, key=_order)
    ]
    out_t = []
    for i, nt, claimed in t_info:
        t = nt.tenant
        received = paid.get(f"t{i}:small", 0) + paid.get(f"t{i}:dated", 0)
        power = opposing_power(t, base_date).value
        assume = assumed_amount(t, power, claimed, received).value if power is not None else None
        out_t.append({"name": nt.name, "deposit_krw": t.deposit_krw, "received_krw": received,
                      "assume_krw": assume, "power": power, "claimed": claimed})  # fmt: skip
    return {
        "price_krw": sale_price_krw,
        "rows": rows,
        "surplus_krw": res.value["surplus_krw"] if res.value else 0,
        "tenants": out_t,
        "unknown": unknown,
    }


_KIND_ORDER = {"cost": 0, "top_priority": 1, "local_tax": 2, "dated": 3, "general": 4}


def _order(c: Claim) -> tuple[int, str]:
    return (_KIND_ORDER[c.kind], str(c.rank_date or ""))
