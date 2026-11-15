"""새로 활용신청한 공공 자료를 한 번씩만 불러 「받을 수 있는지 · 칸이 무엇인지」 보기(11/15).

    uv run python -m aucs_workers.collectors.probe_public

- DB 에 아무것도 넣지 않음. 결과는 logs/probe_public.log (칸 이름 · 건수 · 첫 줄 · 오류 글, 키는 가림).
- 주소 · 버전을 모르는 것은 후보를 차례로 불러 봄. 범위: 용인 수지구(41465), 자료마다 몇 줄.
- 수집기를 붙이고 나면 이 파일은 지움.
"""

import json
import os
import sys
import time
from datetime import date, datetime
from typing import Any

import httpx
import xmltodict

from aucs_workers.db import ROOT

LOG = ROOT / "logs" / "probe_public.log"
GOV = "https://apis.data.go.kr"
SGG = "41465"  # 용인시 수지구
GAP = 1.0


def first_rows(d: Any) -> tuple[list[dict[str, Any]], Any]:
    """응답에서 줄 목록(dict 의 list)과 전체 건수를 찾아냄 — 자료마다 껍데기가 달라 깊이 훑음."""
    total: Any = None
    best: list[dict[str, Any]] = []
    stack = [d]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("totalCount", "matchCount", "list_total_count") and total is None:
                    total = v
                if k in ("item", "row") and isinstance(v, dict) and not best:
                    best = [v]
                stack.append(v)
        elif isinstance(x, list):
            if (
                x
                and all(isinstance(i, dict) for i in x)
                and len(x[0]) > len(best[0] if best else {})
            ):
                best = x
            stack.extend(x)
    return best, total


def call(client: httpx.Client, out: list[str], label: str, url: str, params: dict[str, Any],
         secrets: list[str]) -> list[dict[str, Any]]:  # fmt: skip
    time.sleep(GAP)
    try:
        r = client.get(url, params=params)
        body = (r.text or "").strip()
    except httpx.HTTPError as e:
        out.append(f"[{label}] 연결 실패: {type(e).__name__}")
        return []
    for s in secrets:
        body = body.replace(s, "***") if s else body
    try:
        d = xmltodict.parse(body) if body.startswith("<") else json.loads(body)
    except Exception:  # noqa: BLE001
        out.append(f"[{label}] HTTP {r.status_code} · 못 읽음: {body[:200]}")
        return []
    rows, total = first_rows(d)
    if not rows:
        out.append(
            f"[{label}] HTTP {r.status_code} · 줄 없음: {json.dumps(d, ensure_ascii=False)[:300]}"
        )
        return []
    out.append(f"[{label}] HTTP {r.status_code} · 전체 {total} · 받은 줄 {len(rows)}")
    out.append(f"   칸({len(rows[0])}): {', '.join(rows[0].keys())}")
    out.append(f"   첫 줄: {json.dumps(rows[0], ensure_ascii=False)[:700]}")
    return rows


def redev() -> None:
    """정비사업 공식 자료 표본(11/15): 서울 열린데이터광장 두 자료 · 경기데이터드림. 키가 없으면 견본 키(5줄)."""
    seoul = os.getenv("SEOUL_OPENAPI_KEY", "").strip().strip("\"'") or "sample"
    gg = os.getenv("GG_OPENAPI_KEY", "").strip().strip("\"'")
    sec = [seoul if seoul != "sample" else "", gg]
    out = [f"=== {datetime.now():%Y-%m-%d %H:%M} 정비사업 공식 자료 표본 (서울 키 {'있음' if seoul != 'sample' else '견본'} · 경기 키 {'있음' if gg else '견본'})"]  # fmt: skip
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        out.append("\n# 서울 도시정비사업 통계(OA-22856) · 서울플랜+ 정비사업 현황(OA-23112)")
        for svc in ("TbSeoulRedevStatus", "vnBsnsNmtn"):
            rows = call(
                c,
                out,
                f"서울 {svc}",
                f"http://openapi.seoul.go.kr:8088/{seoul}/json/{svc}/1/5/",
                {},
                sec,
            )
            for r in rows[1:3]:
                out.append(f"   다음 줄: {json.dumps(r, ensure_ascii=False)[:700]}")
        out.append("\n# 경기도 일반 정비 사업 추진 현황(경기데이터드림)")
        for svc in ("TBKINTEXHOTELLISTM", "GenrlImprvBizpropls"):
            params: dict[str, Any] = {"Type": "json", "pIndex": 1, "pSize": 5}
            if gg:
                params["KEY"] = gg
            rows = call(c, out, f"경기 {svc}", f"https://openapi.gg.go.kr/{svc}", params, sec)
            for r in rows[1:3]:
                out.append(f"   다음 줄: {json.dumps(r, ensure_ascii=False)[:900]}")
            if rows:
                break
    log = LOG.with_name("probe_redev.log")
    log.parent.mkdir(exist_ok=True)
    log.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"끝: {log}")


def main() -> None:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    rone = os.getenv("RONE_API_KEY", "").strip().strip("\"'")
    sec = [key, rone]
    out = [f"=== {datetime.now():%Y-%m-%d %H:%M} 공공 자료 표본 (키: 공공데이터 {'있음' if key else '없음'} · R-ONE {'있음' if rone else '없음'})"]  # fmt: skip
    ym = f"{date.today().year}{date.today().month - 1 or 12:02d}"
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        out.append("\n# 1. 토지 매매 실거래가")
        call(c, out, "토지 매매", f"{GOV}/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
             {"serviceKey": key, "LAWD_CD": SGG, "DEAL_YMD": ym, "numOfRows": 5, "pageNo": 1}, sec)  # fmt: skip

        out.append("\n# 2. 공동주택 단지 목록")
        apts: list[dict[str, Any]] = []
        for svc, op in (
            ("AptListService4", "getSigunguAptList4"),
            ("AptListService3", "getSigunguAptList3"),
        ):
            apts = call(c, out, f"단지 목록 {svc}", f"{GOV}/1613000/{svc}/{op}",
                        {"serviceKey": key, "sigunguCode": SGG, "numOfRows": 5, "pageNo": 1}, sec)  # fmt: skip
            if apts:
                break
        code = next((a.get("kaptCode") for a in apts if a.get("kaptCode")), None)

        out.append("\n# 3. 공동주택 기본 정보 · 상세 정보")
        if code:
            for svc, op in (
                ("AptBasisInfoServiceV5", "getAphusBassInfoV5"),
                ("AptBasisInfoServiceV4", "getAphusBassInfoV4"),
            ):
                if call(
                    c,
                    out,
                    f"기본 정보 {svc}",
                    f"{GOV}/1613000/{svc}/{op}",
                    {"serviceKey": key, "kaptCode": code},
                    sec,
                ):
                    call(c, out, f"상세 정보 {svc}", f"{GOV}/1613000/{svc}/{op.replace('Bass', 'Dtl')}",
                         {"serviceKey": key, "kaptCode": code}, sec)  # fmt: skip
                    break
        else:
            out.append("단지 코드를 못 받아 건너뜀")

        out.append("\n# 4. 공동주택 단지 식별정보(한국부동산원)")
        try:
            time.sleep(GAP)
            oas = c.get(
                "https://infuser.odcloud.kr/oas/docs", params={"namespace": "AptIdInfoSvc/v1"}
            ).json()
            paths = list((oas.get("paths") or {}).keys())
            out.append(f"명세의 주소: {paths} · 서버 {oas.get('host')}{oas.get('basePath')}")
        except Exception as e:  # noqa: BLE001
            paths = []
            out.append(f"명세 못 받음({type(e).__name__}) — 후보로 불러 봄")
        for op in sorted(
            {p.rsplit("/", 1)[-1] for p in paths} | {"getAptInfo", "getDongInfo", "getHistInfo"}
        ):
            call(
                c,
                out,
                f"식별정보 {op}",
                f"https://api.odcloud.kr/api/AptIdInfoSvc/v1/{op}",
                {"serviceKey": key, "page": 1, "perPage": 3},
                sec,
            )

        out.append("\n# 5. 상가(상권)정보")
        call(c, out, "상권 · 시군구", f"{GOV}/B553077/api/open/sdsc2/storeListInDong",
             {"serviceKey": key, "divId": "signguCd", "key": SGG, "numOfRows": 3, "pageNo": 1, "type": "json"}, sec)  # fmt: skip
        call(c, out, "상권 · 반경 300m", f"{GOV}/B553077/api/open/sdsc2/storeListInRadius",
             {"serviceKey": key, "radius": 300, "cx": 127.0952, "cy": 37.3225, "numOfRows": 3, "pageNo": 1, "type": "json"}, sec)  # fmt: skip

        out.append("\n# 6. R-ONE 통계표 목록(임대 · 공실 · 전환율 · 수익률)")
        time.sleep(GAP)
        try:
            r = c.get("https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do",
                      params={"KEY": rone, "Type": "json", "pIndex": 1, "pSize": 1000})  # fmt: skip
            rows, total = first_rows(r.json())
            hit = [
                x
                for x in rows
                if any(
                    w in str(x.get("STATBL_NM", "")) for w in ("임대", "공실", "전환율", "수익률")
                )
            ]
            out.append(
                f"HTTP {r.status_code} · 전체 {total} · 받은 줄 {len(rows)} · 맞는 표 {len(hit)}"
            )
            if rows:
                out.append(f"   칸: {', '.join(rows[0].keys())}")
            for x in hit[:80]:
                out.append(
                    f"   {x.get('STATBL_ID')} | {x.get('DTACYCLE_CD')} | {x.get('STATBL_NM')}"
                )
            if not rows:
                out.append(f"   응답: {r.text.replace(rone, '***')[:300]}")
        except Exception as e:  # noqa: BLE001
            out.append(f"R-ONE 실패: {type(e).__name__}")
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"끝: {LOG}")


if __name__ == "__main__":
    redev() if "--redev" in sys.argv else main()
