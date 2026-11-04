"""국토부 실거래가 수집 (서울·경기·인천) → core.trades.

    uv run python -m aucs_workers.collectors.trades --months 3     # 매달: 최근 3개월 다시 (늦은 신고·해제 반영)

- 다시 받은 (시군구, 달, 유형) 은 지우고 새로 넣음 → 몇 번 돌려도 중복 없음
- 해제된 거래(cdealType=O)는 넣지 않음, 금액은 원 단위(API 는 만원)
- 전월세는 최근 1년만 둠 (무료 DB 한도, 10/17 결정)
- 원본(raw) 저장은 DB 용량 때문에 Pro 전환 전까지 하지 않음
- data.go.kr 초당 제한: 초당 5회, 하루 한도에 닿으면 받은 것만 저장하고 멈춤
"""

import argparse
import json
import os
import time
from datetime import date, timedelta
from typing import Any
from urllib.parse import unquote

import httpx
import psycopg
import xmltodict

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

BASE = "https://apis.data.go.kr/1613000"
# 유형: (서비스, 오퍼레이션, deal_kind, prop_type)
TYPES = {
    "apt_sale": ("RTMSDataSvcAptTrade", "getRTMSDataSvcAptTrade", "sale", "apt"),
    "apt_lease": ("RTMSDataSvcAptRent", "getRTMSDataSvcAptRent", "lease", "apt"),
    "rowhouse_sale": ("RTMSDataSvcRHTrade", "getRTMSDataSvcRHTrade", "sale", "rowhouse"),
    "rowhouse_lease": ("RTMSDataSvcRHRent", "getRTMSDataSvcRHRent", "lease", "rowhouse"),
    "house_sale": ("RTMSDataSvcSHTrade", "getRTMSDataSvcSHTrade", "sale", "house"),
    "house_lease": ("RTMSDataSvcSHRent", "getRTMSDataSvcSHRent", "lease", "house"),
    "officetel_sale": ("RTMSDataSvcOffiTrade", "getRTMSDataSvcOffiTrade", "sale", "officetel"),
    "officetel_lease": ("RTMSDataSvcOffiRent", "getRTMSDataSvcOffiRent", "lease", "officetel"),
    "commercial_sale": ("RTMSDataSvcNrgTrade", "getRTMSDataSvcNrgTrade", "sale", "commercial"),
}
GAP = 0.2  # 초당 5회


class ApiError(Exception):
    pass


def _int(v: Any) -> int | None:
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_trade(
    it: dict[str, Any], deal_kind: str, prop_type: str, sgg: str, region: dict[tuple[str, str], str]
) -> dict[str, Any] | None:
    """API 한 줄 → core.trades 한 줄. 해제 거래·날짜 없는 줄은 None."""
    if str(it.get("cdealType") or "").strip() == "O":
        return None
    y, m, d = _int(it.get("dealYear")), _int(it.get("dealMonth")), _int(it.get("dealDay"))
    if not (y and m and d):
        return None
    dong = str(it.get("umdNm") or "").strip()
    man = 10_000
    pre = _int(it.get("preDeposit"))
    dep, rent, price = (
        _int(it.get("deposit")),
        _int(it.get("monthlyRent")),
        _int(it.get("dealAmount")),
    )
    return {
        "deal_kind": deal_kind,
        "prop_type": prop_type,
        "sub_type": it.get("houseType") or it.get("buildingUse") or None,
        "sigungu_code": sgg,
        "region_code": region.get((sgg, dong))
        or region.get((sgg, dong.split(" ")[0])),  # 「진접읍 금곡리」 → 읍 코드
        "dong_name": dong or None,
        "complex_name": it.get("aptNm") or it.get("mhouseNm") or it.get("offiNm") or None,
        "lot_no": it.get("jibun") or None,
        "area_m2": _float(it.get("excluUseAr") or it.get("buildingAr") or it.get("totalFloorAr")),
        "land_area_m2": _float(it.get("landAr") or it.get("plottageAr")),
        "floor": _int(it.get("floor")),
        "build_year": _int(it.get("buildYear")),
        "deal_date": date(y, m, d),
        "price_krw": price * man if price is not None and deal_kind == "sale" else None,
        "deposit_krw": dep * man if dep is not None else None,
        "monthly_rent_krw": rent * man if rent is not None else None,
        "contract_kind": it.get("contractType") or None,
        "prev_deposit_krw": pre * man if pre is not None else None,
    }


def months_back(n: int, today: date) -> list[str]:
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def fetch(
    client: httpx.Client, key: str, svc: str, op: str, lawd: str, ym: str
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        time.sleep(GAP)
        r = client.get(
            f"{BASE}/{svc}/{op}",
            params={
                "serviceKey": key,
                "LAWD_CD": lawd,
                "DEAL_YMD": ym,
                "numOfRows": 1000,
                "pageNo": page,
            },
        )
        body = (r.text or "").strip()
        if not body or body.startswith(("Forbidden", "Unexpected", "API not found")):
            raise ApiError(body[:80] or "빈 응답")
        d = xmltodict.parse(body) if body.startswith("<") else json.loads(body)
        if "OpenAPI_ServiceResponse" in d:
            h = d["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
            raise ApiError(
                f"{h.get('returnReasonCode')} {h.get('returnAuthMsg') or h.get('errMsg')}"
            )
        resp = d.get("response", {})
        if str(resp.get("header", {}).get("resultCode", "")) not in ("00", "000", "0"):
            raise ApiError(str(resp.get("header", {}).get("resultMsg")))
        b = resp.get("body") or {}
        part = (b.get("items") or {}).get("item") or []
        items += [part] if isinstance(part, dict) else part
        if page * 1000 >= int(b.get("totalCount") or 0) or not part:
            return items
        page += 1


COLS = ["deal_kind", "prop_type", "sub_type", "sigungu_code", "region_code", "dong_name", "complex_name", "lot_no",
        "area_m2", "land_area_m2", "floor", "build_year", "deal_date", "price_krw", "deposit_krw", "monthly_rent_krw",
        "contract_kind", "prev_deposit_krw"]  # fmt: skip


def save(
    conn: psycopg.Connection,
    deal_kind: str,
    prop_type: str,
    sgg: str,
    ym: str,
    rows: list[dict[str, Any]],
) -> None:
    first = date(int(ym[:4]), int(ym[4:]), 1)
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    conn.execute(
        "delete from core.trades where deal_kind=%s and prop_type=%s and sigungu_code=%s and deal_date >= %s and deal_date < %s",
        (deal_kind, prop_type, sgg, first, nxt),
    )
    with (
        conn.cursor() as cur,
        cur.copy(f"copy core.trades ({', '.join(COLS)}, fetched_at) from stdin") as cp,
    ):
        for r in rows:
            cp.write_row([r[c] for c in COLS] + [time.strftime("%Y-%m-%d %H:%M:%S%z")])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--types", nargs="*", default=list(TYPES))
    ap.add_argument(
        "--sido", help="이 시도만(예: 인천광역시) — 새로 더한 지역을 몇 년치 채울 때(11/4)"
    )
    a = ap.parse_args()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key  # Encoding 키를 넣어도 Decoding 키로
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    today = date.today()
    yms = months_back(a.months, today)
    with connect() as conn, run(conn, "trades", "실거래가") as job:
        sggs = [r[0] for r in conn.execute(
            "select distinct sigungu_code from ref.regions where level = 'sigungu' and sigungu_code is not null"
            " and (%s::text is null or sido = %s)", (a.sido, a.sido)).fetchall()]  # fmt: skip
        sggs = [
            c
            for c in sggs
            if not (c.endswith("0") and any(o != c and o[:4] == c[:4] for o in sggs))
        ]  # 구가 있는 시는 구 단위로
        region = {(s, e): rc for rc, s, e in conn.execute(
            "select region_code, sigungu_code, eupmyeondong from ref.regions where level = 'dong'").fetchall()}  # fmt: skip
        with httpx.Client(timeout=30) as client:
            for name in a.types:
                svc, op, kind, prop = TYPES[name]
                n = 0
                for sgg in sggs:
                    for ym in yms:
                        rows = [
                            t
                            for it in fetch(client, key, svc, op, sgg, ym)
                            if (t := parse_trade(it, kind, prop, sgg, region))
                        ]
                        save(conn, kind, prop, sgg, ym, rows)
                        conn.commit()
                        n += len(rows)
                job.count += n
                print(f"  {name} {n:,}")
        conn.execute(
            "delete from core.trades where deal_kind = 'lease' and deal_date < %s",
            (today - timedelta(days=365),),
        )
        conn.commit()
    print(f"끝: {job.count:,}건")


if __name__ == "__main__":
    main()
