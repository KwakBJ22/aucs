"""예정물건 — 법원 「배당요구종기공고」 받기(11/27 대표님: 탱크옥션처럼 매각공고 전 사건을 먼저).

경매개시결정 뒤 법원이 사건마다 배당요구종기를 공고함 → 매각공고(물건 목록)는 그 뒤 몇 달 지나 나옴.
그 사이 사건을 core.upcoming_cases 에 둠. 화면(PGJ142M01)과 같은 요청, 로그인 없음.
법원마다 담당계 목록 1번 + 담당계마다 1번(서울 · 경기 · 인천 16법원 약 170번, 하루 한 번 — court_hourly).
이름(소유자 · 채무자 · 채권자)은 원본(raw.court_notice_raw)에만 남고 core 표에는 넣지 않음.

    python -m aucs_workers.collectors.court_notices            # 16법원
    python -m aucs_workers.collectors.court_notices --court B000210
"""

import argparse
import re
from datetime import date
from typing import Any

import psycopg
from aucs_rules.courts import COURTS

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_docs import JS_POST
from aucs_workers.collectors.polite import DailyLimitReached, Polite
from aucs_workers.collectors.store import save_raw
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

NOTICE_PAGE = (
    "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ141M00.xml&pgjId=142M01"
)
DEPT_PATH = "/pgj/pgj002/selectCortOfcDeptLst.on"
LIST_PATH = "/pgj/pgj142/searchDstrtDemnLstprdPbanc.on"
SEARCH_KEYS = ("csNo intrpsNm rprsAdongSdCd rprsAdongSggCd rprsAdongEmdCd dspslObjctRdnmSdCd "
               "dspslObjctRdnmSggCd consonant dspslObjctRdnmNo").split()  # fmt: skip


def _ymd(v: Any) -> date | None:
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None


def _txt(v: Any) -> str | None:
    s = re.sub(r"\s+", " ", str(v or "")).strip()
    return s or None


def dept_codes(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """담당계 목록 응답 → [(코드, 이름)] — 경매계만(「(보존)」 · 관리자 뺌). 응답 칸 이름이 바뀌어도 코드 · 이름 꼴로 찾음."""
    out: list[tuple[str, str]] = []
    for r in rows:
        code = next((str(r[k]) for k in ("code", "jdbnCd", "deptCd", "cd") if r.get(k)), "")
        name = next((str(r[k]) for k in ("name", "jdbnNm", "deptNm", "nm") if r.get(k)), "")
        if code and name.startswith("경매") and "보존" not in name:
            out.append((code, name))
    return out


def parse_notice(court: str, dept: str, r: dict[str, Any]) -> dict[str, Any] | None:
    """공고 한 줄 → core.upcoming_cases 한 줄(이름 칸은 넣지 않음). 사건번호가 없으면 None."""
    case_no = _txt(r.get("userCsNo"))
    if not case_no:
        return None
    dong = " ".join(x for x in (_txt(r.get("adongEmdNm")), _txt(r.get("adongRiNm"))) if x) or None
    road = " ".join(
        x for x in (_txt(r.get("RDNM")), _txt(r.get("rdnmBldNo")), _txt(r.get("rdnmRefcAddr"))) if x
    )
    cnt = re.sub(r"\D", "", str(r.get("mgakMokmulCnt") or ""))
    return {
        "court_code": court,
        "case_no": case_no,
        "dept_code": dept,
        "ordered_date": _ymd(r.get("csCmdcYmd")),
        "claim_deadline": _ymd(r.get("dstrtDemnLstprdYmd")),
        "notice_date": _ymd(r.get("dstrtDemnLstprdPbancYmd")),
        "sido": _txt(r.get("adongSdNm")),
        "sigungu": _txt(r.get("adongSggNm")),
        "dong": dong,
        "lot_no": _txt(r.get("rprsLtnoAddr")),
        "road_address": road or None,
        "building_name": _txt(r.get("bldNm")),
        "building_detail": _txt(r.get("bldDtlDts")),
        "item_count": int(cnt) if cnt else None,
        "list_kind": _txt(r.get("auctnLstDvsCd")),
    }


_COLS = ["court_code", "case_no", "dept_code", "ordered_date", "claim_deadline", "notice_date", "sido",
         "sigungu", "dong", "lot_no", "road_address", "building_name", "building_detail", "item_count",
         "list_kind"]  # fmt: skip
_UPSERT = (
    f"insert into core.upcoming_cases ({', '.join(_COLS)}) values ({', '.join('%(' + c + ')s' for c in _COLS)}) "
    "on conflict (court_code, case_no) do update set "
    + ", ".join(f"{c} = coalesce(excluded.{c}, core.upcoming_cases.{c})" for c in _COLS[2:])
    + ", last_seen_at = now()"
)


# 부동산(01 토지 · 02 건물 · 03 집합건물)만 지역 코드 — 물건과 같은 함수, 같은 단지 실거래를 붙이는 열쇠(이주 0088)
REAL_ESTATE = ("01", "02", "03")
_REGION = """update core.upcoming_cases
   set region_code = ref.region_code_for(null, concat_ws(' ', sido, sigungu, split_part(dong, ' ', 1)))
 where region_code is null and list_kind = any(%s)"""


def save(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> int:
    with conn.cursor() as cur:
        cur.executemany(_UPSERT, rows)
        cur.execute(_REGION, (list(REAL_ESTATE),))
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--court", help="이 법원 코드만(예: B000210)")
    a = ap.parse_args()
    courts = {a.court: COURTS[a.court]} if a.court else COURTS
    polite = Polite(hourly=False)
    from playwright.sync_api import sync_playwright

    with connect() as conn, run(conn, "court_notices", "예정물건(배당요구종기공고)") as job:
        with sync_playwright() as p:
            browser = launch_chrome(p)
            page = browser.new_page()
            page.goto(NOTICE_PAGE, wait_until="networkidle", timeout=60000)

            def post(path: str, body: dict[str, Any], label: str) -> dict[str, Any]:
                res = polite.call(lambda: dict(page.evaluate(JS_POST, [path, body])), label)
                return dict(res.get("data") or {})

            try:
                for court, name in courts.items():
                    depts = dept_codes(
                        post(DEPT_PATH, {"cortOfcCd": court}, f"{name} 담당계").get(
                            "cortOfcDeptLst"
                        )
                        or []
                    )
                    got = 0
                    for code, dname in depts:
                        srch = {k: "" for k in SEARCH_KEYS}
                        srch.update({"jdbnDeptCortOfcCd": court, "jdbnCd": code, "dvsFlag": "C"})
                        raw = (
                            post(LIST_PATH, {"dma_srchLstprdPbanc": srch}, f"{name} {dname}").get(
                                "dlt_lstprdPbancCorOfc"
                            )
                            or []
                        )
                        save_raw(
                            conn,
                            "court_notice_raw",
                            court,
                            [dict(r, docid=r.get("csNo") or "") for r in raw],
                        )
                        rows = [x for x in (parse_notice(court, code, r) for r in raw) if x]
                        got += save(conn, rows)
                        conn.commit()
                    job.count += got
                    print(f"  {name} 담당계 {len(depts)} · 공고 {got}건", flush=True)
                    polite.between_cases()
            except DailyLimitReached as e:
                print(f"  멈춤: {e}", flush=True)
            finally:
                browser.close()
    print(f"끝: {job.count:,}건")


if __name__ == "__main__":
    main()
