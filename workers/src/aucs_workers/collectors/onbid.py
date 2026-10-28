"""공매(온비드, 한국자산관리공사) 수집 → raw.onbid_raw(원본) + core.onbid_*(정리). 경매와 표를 따로 둠.

    uv run python -m aucs_workers.collectors.onbid                    # 아침 묶음: 물건·공고·지난 7일 결과
    uv run python -m aucs_workers.collectors.onbid --result-days 60   # 처음 한 번: 결과 60일치

규칙(경매레이더 collectors/onbid SKILL, 9/8 실측)
  물건  OnbidRlstListSrvc2/getRlstCltrList2   진행·예정. pvctTrgtYn=N 필수(빠지면 코드 11). 서울·경기 시도 단위로 끝까지
  공고  OnbidPbancListSrvc2/getPbancList2      공고일(pbancYmd) — 「새 물건」은 공고일 기준(압류재산은 2주에 한 번 몰아 개찰)
  결과  OnbidCltrBidRsltListSrvc2/getCltrBidRsltList2  개찰 끝난 회차만. 통계용이라 전국
  재산유형은 v2 신코드만(구코드는 0건 허수). 일정 미정은 2999·9999년 → 비움. 최저가율은 직접 계산.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import unquote

import httpx
import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.onbid_parse import (
    KST,
    current_round,
    parse_item,
    parse_notice,
    parse_result,
)
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

BASE = "https://apis.data.go.kr/B010003"
PRPT_ALL = "0007,0010,0005,0004,0002,0003,0006,0008,0011,0013"
SIDO = ["서울특별시", "경기도"]
GAP = 0.3  # 초당 3회쯤
ROWS = 1000


HINT = {
    "30": "이 API 활용신청이 안 됨 — data.go.kr 에서 신청",
    "31": "서비스키 기간 만료",
    "22": "하루 한도 넘음 — 내일 다시",
    "12": "서비스 없음 — 주소 확인",
    "11": "필수 칸 빠짐",
    "_": "활용신청이 안 됐거나 아직 반영 전일 수 있음",
}


class ApiError(Exception):
    def __init__(self, msg: str, code: str = "") -> None:
        super().__init__(f"{code} {msg}".strip())
        self.code = code


def _items(node: Any) -> tuple[list[dict[str, Any]], int | None]:
    """응답 어디에 있든 item 목록과 totalCount 를 찾음(v2 응답 모양 차이 흡수)."""
    total: int | None = None
    items: list[dict[str, Any]] | None = None
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            for k, v in n.items():
                if k.lower() == "totalcount":
                    try:
                        total = int(v)
                    except (TypeError, ValueError):
                        pass
                if k == "item":
                    items = v if isinstance(v, list) else [v]
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(n, list):
            stack.extend(n)
    return (items or []), total


def _result_code(d: Any) -> tuple[str, str]:
    """응답 어디에 있든 resultCode·resultMsg(공공데이터포털 게이트웨이 오류는 맨 바깥에 옴)."""
    stack = [d]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            for k in ("resultCode", "returnReasonCode", "errCd"):
                if k in n and n[k] not in (None, ""):
                    m = n.get("resultMsg") or n.get("returnAuthMsg") or n.get("errMsg") or ""
                    return str(n[k]), str(m)
            stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
        elif isinstance(n, list):
            stack.extend(n)
    return "00", ""


def call(
    client: httpx.Client, key: str, path: str, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    for attempt in range(6):
        time.sleep(GAP)
        try:
            r = client.get(
                f"{BASE}/{path}", params={"serviceKey": key, "resultType": "json", **params}
            )
        except httpx.HTTPError:
            time.sleep(2 * (attempt + 1))
            continue
        body = (r.text or "").strip()
        if not body:
            raise ApiError("빈 응답 — 활용신청을 확인하세요", "EMPTY")
        if body.startswith("<"):
            # 게이트웨이 오류는 JSON 을 달라고 해도 XML 로 옴: <returnReasonCode>30</returnReasonCode> 등
            m = re.search(r"<(?:returnReasonCode|resultCode)>(\w+)<", body)
            t = re.search(r"<(?:returnAuthMsg|resultMsg)>([^<]+)<", body)
            raise ApiError(t.group(1) if t else body[:160], m.group(1) if m else "XML")
        try:
            d = json.loads(body)
        except json.JSONDecodeError:
            raise ApiError(body[:160], "JSON") from None
        s = json.dumps(d, ensure_ascii=False)
        if "초당" in s or "PER_SECOND" in s or "LIMITED_NUMBER" in s:
            time.sleep(2 * (attempt + 1))
            continue
        code, msg = _result_code(d)
        if code not in ("00", "000", "0"):
            raise ApiError(msg or "오류", code)
        items, total = _items(d)
        if total is None and not items:
            # 목록도 건수도 없는 응답 = 알아보지 못한 모양(활용신청 전 안내 등). 0건으로 넘기지 않음(10/28)
            raise ApiError("알 수 없는 응답: " + body[:200], "SHAPE")
        return items, (total if total is not None else len(items))
    raise ApiError("초당 호출 제한이 계속 걸림", "RATE")


def pages(
    client: httpx.Client, key: str, path: str, params: dict[str, Any], label: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        items, total = call(client, key, path, {**params, "numOfRows": ROWS, "pageNo": page})
        out += items
        print(f"\r  {label} {len(out):,}/{total:,}", end="", flush=True)
        if not items or len(out) >= total:
            print(flush=True)
            return out
        page += 1


def save_raw(cur: psycopg.Cursor[Any], kind: str, key: str, payload: dict[str, Any]) -> None:
    cur.execute(
        "insert into raw.onbid_raw (kind, key, payload) values (%s, %s, %s) "
        "on conflict (kind, key) do update set payload = excluded.payload, fetched_at = now()",
        (kind, key, Jsonb(payload)),
    )


_ITEM_COLS = [
    "item_id", "mng_no", "kind", "kind_name", "disposal", "title", "address", "sido", "sigungu", "dong",
    "lot_no", "usage_name", "land_m2", "building_m2", "appraisal_krw", "min_price_krw", "failed_count",
    "bid_start", "bid_end", "open_at", "status_name", "notice_no",
]  # fmt: skip
_ITEM = (
    f"insert into core.onbid_items ({', '.join(_ITEM_COLS)}, region_code, status_code, fetched_at, checked_at) values ("
    + ", ".join(f"%({c})s" for c in _ITEM_COLS)
    + ", ref.region_code_for(%(pnu_region)s, %(address)s), 'active', now(), now())"
    + " on conflict (item_id) do update set "
    + ", ".join(f"{c} = excluded.{c}" for c in _ITEM_COLS[2:])
    + ", region_code = excluded.region_code, status_code = 'active', fetched_at = now(), checked_at = now()"
    + ", updated_at = case when ("
    + ", ".join(f"core.onbid_items.{c}" for c in _ITEM_COLS[2:])
    + ") is distinct from ("
    + ", ".join(f"excluded.{c}" for c in _ITEM_COLS[2:])
    + ") then now() else core.onbid_items.updated_at end"
)
_ROUND = """insert into core.onbid_rounds (item_id, cond_no, bid_start, bid_end, open_at, min_price_krw, status_name, checked_at)
values (%(item_id)s, %(cond_no)s, %(bid_start)s, %(bid_end)s, %(open_at)s, %(min_price_krw)s, %(status_name)s, now())
on conflict (item_id, cond_no) do update set bid_start = excluded.bid_start, bid_end = excluded.bid_end,
  open_at = excluded.open_at, min_price_krw = excluded.min_price_krw, status_name = excluded.status_name, checked_at = now()"""


def save_items(
    conn: psycopg.Connection[Any], raw: list[dict[str, Any]], complete: bool
) -> tuple[int, int]:
    """한 줄 = 한 회차 → 물건별로 묶어 지금 회차를 물건 줄에. 매각만 화면에 쓰지만 원본은 다 남김."""
    now = datetime.now(KST)
    by: dict[str, list[dict[str, Any]]] = {}
    with conn.cursor() as cur:
        for r in raw:
            p = parse_item(r)
            if not p:
                continue
            save_raw(cur, "item", f"{p['mng_no']}|{p['cond_no']}", r)
            by.setdefault(p["item_id"], []).append(p)
        for _, rounds in by.items():
            cur.execute(_ITEM, current_round(rounds, now))
            for x in rounds:
                if x["cond_no"]:
                    cur.execute(_ROUND, x)
        gone = 0
        if (
            complete and by
        ):  # 서울·경기를 끝까지 받았을 때만: 이번에 안 나온 진행 물건 = 온비드 목록에서 빠짐
            cur.execute(
                "update core.onbid_items set status_code = 'gone', updated_at = now() "
                "where status_code = 'active' and not (item_id = any(%s))",
                (list(by),),
            )
            gone = cur.rowcount
    conn.commit()
    return len(by), gone


_LINK_SQL = """
select o.item_id, coalesce(o.address, '') || ' ' || coalesce(o.title, ''), i.item_id, coalesce(i.address, '')
from core.onbid_items o
join core.items i on i.region_code = o.region_code and replace(i.lot_no, ' ', '') = o.lot_no
where o.status_code = 'active' and o.lot_no is not null and i.sale_date >= current_date
"""


def link_same_house(conn: psycopg.Connection[Any]) -> int:
    """같은 집이 법원 경매에도 나와 있으면 core.item_links 에 잇기. 지번이 같고 동·호수까지 맞을 때만."""
    from aucs_rules.building import same_unit

    rows = conn.execute(_LINK_SQL).fetchall()
    pairs = {(r[2], r[0]) for r in rows if same_unit(r[1], r[3])}
    with conn.cursor() as cur:
        cur.execute("delete from core.item_links")
        cur.executemany(
            "insert into core.item_links (court_item_id, onbid_item_id) values (%s, %s) on conflict do nothing",
            sorted(pairs),
        )
    conn.commit()
    return len(pairs)


def save_notices(conn: psycopg.Connection[Any], raw: list[dict[str, Any]]) -> int:
    n = 0
    with conn.cursor() as cur:
        for r in raw:
            p = parse_notice(r)
            if not p:
                continue
            save_raw(cur, "notice", p["notice_no"], r)
            cur.execute(
                "insert into core.onbid_notices (notice_no, notice_date, name, org_name, kind_name) "
                "values (%(notice_no)s, %(notice_date)s, %(name)s, %(org_name)s, %(kind_name)s) "
                "on conflict (notice_no) do update set notice_date = excluded.notice_date, name = excluded.name, "
                "org_name = excluded.org_name, kind_name = excluded.kind_name, fetched_at = now()",
                p,
            )
            n += 1
    conn.commit()
    return n


_RESULT_COLS = [
    "mng_no", "opened_at", "notice_no", "item_seq", "kind_name", "disposal", "usage_l", "usage_m", "usage_s",
    "title", "sido", "land_m2", "building_m2", "appraisal_krw", "min_price_krw", "win_krw", "failed_round",
    "bidders", "invalid_bidders", "rate_appraisal", "rate_min", "result", "source",
]  # fmt: skip
RESULT_SQL = (
    f"insert into core.onbid_results ({', '.join(_RESULT_COLS)}) values ("
    + ", ".join(f"%({c})s" for c in _RESULT_COLS)
    + ") on conflict (mng_no, opened_at, notice_no) do update set "
    + ", ".join(f"{c} = excluded.{c}" for c in _RESULT_COLS[3:])
    + ", loaded_at = now()"
)


def save_results(conn: psycopg.Connection[Any], raw: list[dict[str, Any]]) -> int:
    n = 0
    with conn.cursor() as cur:
        for r in raw:
            p = parse_result(r)
            if not p:
                continue
            save_raw(
                cur, "result", f"{p['mng_no']}|{p['opened_at']:%Y%m%d%H%M}|{p['notice_no']}", r
            )
            cur.execute(RESULT_SQL, p)
            n += 1
    conn.commit()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["items", "notices", "results"])
    ap.add_argument(
        "--result-days", type=int, default=7, help="입찰결과를 며칠 받을지(전국, 처음엔 60)"
    )
    a = ap.parse_args()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    jobs = [a.only] if a.only else ["items", "notices", "results"]
    today = date.today()
    failed: list[str] = []
    with connect() as conn, run(conn, "onbid", "공매(온비드)") as job:
        with httpx.Client(timeout=60, headers={"Accept": "application/json"}) as client:
            for j in jobs:
                try:
                    if j == "items":
                        raw: list[dict[str, Any]] = []
                        for sd in SIDO:
                            raw += pages(client, key, "OnbidRlstListSrvc2/getRlstCltrList2",
                                         {"prptDivCd": PRPT_ALL, "pvctTrgtYn": "N", "lctnSdnm": sd}, f"물건 {sd}")  # fmt: skip
                        n, gone = save_items(conn, raw, complete=True)
                        job.count += n
                        print(
                            f"[물건] {len(raw):,}줄 → {n:,}건 · 목록에서 빠짐 {gone:,}건",
                            flush=True,
                        )
                        print(f"[같은 집 경매] {link_same_house(conn):,}건", flush=True)
                    elif j == "notices":
                        raw = pages(client, key, "OnbidPbancListSrvc2/getPbancList2", {
                            "cltrTypeCd": "0001", "prptDivCd": PRPT_ALL,
                            "opbdDtStart": (today + timedelta(days=1)).strftime("%Y%m%d"),
                            "opbdDtEnd": (today + timedelta(days=183)).strftime("%Y%m%d")}, "공고")  # fmt: skip
                        print(f"[공고] {save_notices(conn, raw):,}건", flush=True)
                    else:
                        n, d = 0, today - timedelta(days=a.result_days)
                        while d < today:  # 열흘씩 나눠 받음(전국이라 많음)
                            e = min(d + timedelta(days=9), today)
                            raw = pages(client, key, "OnbidCltrBidRsltListSrvc2/getCltrBidRsltList2", {
                                "cltrTypeCd": "0001", "prptDivCd": PRPT_ALL,
                                "opbdDtStart": d.strftime("%Y%m%d"), "opbdDtEnd": e.strftime("%Y%m%d")},
                                f"결과 {d:%m-%d}~{e:%m-%d}")  # fmt: skip
                            n += save_results(conn, raw)
                            d = e + timedelta(days=1)
                        print(f"[결과] {n:,}건", flush=True)
                except ApiError as e:
                    conn.rollback()
                    failed.append(j)
                    print(f"\n[건너뜀] {j} — {e} ({HINT.get(e.code, HINT['_'])})", flush=True)
        if failed and len(failed) == len(jobs):
            raise RuntimeError("공매 수집 전부 실패: " + ", ".join(failed))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
