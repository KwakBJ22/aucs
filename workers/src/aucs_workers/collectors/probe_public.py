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
        for svc in ("GenrlimprvBizpropls",):
            params: dict[str, Any] = {"Type": "json", "pIndex": 1, "pSize": 1000 if gg else 5}
            if gg:
                params["KEY"] = gg
            rows = call(c, out, f"경기 {svc}", f"https://openapi.gg.go.kr/{svc}", params, sec)
            for r in rows[1:3]:
                out.append(f"   다음 줄: {json.dumps(r, ensure_ascii=False)[:900]}")
            if rows:
                from collections import Counter

                for col in ("BIZ_STEP_NM", "BIZ_TYPE_NM", "SIGUN_NM"):
                    out.append(
                        f"   {col}: {Counter(str(r.get(col)) for r in rows).most_common(40)}"
                    )
                addr = [str(r.get("LOCPLC_ADDR") or "") for r in rows]
                out.append(
                    f"   주소: 「경기도」로 시작 {sum(a.startswith('경기도') for a in addr)} · 번지 있음 {sum('번지' in a for a in addr)} · 빈 것 {sum(not a for a in addr)}"
                )
                out.append(f"   주소 예: {addr[5:45:4]}")
                for col in (
                    "ASSOCTN_FOUND_CONFMTN_DE",
                    "BIZ_IMPLMTN_CONFMTN_DE",
                    "MANAGE_DISPOSIT_CONFMTN_DE",
                    "STRCONTR_DE",
                    "IMPRV_ZONE_APPONT_FIRST_DE",
                    "PROPLSN_COMMISN_APRV_DE",
                ):
                    vals = [str(r.get(col)) for r in rows if r.get(col)]
                    out.append(f"   {col}: 있음 {len(vals)} · 예 {vals[:4]}")
                break
    log = LOG.with_name("probe_redev.log")
    log.parent.mkdir(exist_ok=True)
    log.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"끝: {log}")


def more() -> None:
    """R-ONE 통계표 자료 꼴 · 건축물대장 전유부 표본(11/15) — 이미 되는 키로. logs/probe_more.log"""
    from urllib.parse import unquote

    from aucs_rules.building import parse_jibun

    from aucs_workers.db import connect

    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    rone = os.getenv("RONE_API_KEY", "").strip().strip("\"'")
    sec = [key, rone]
    out = [f"=== {datetime.now():%Y-%m-%d %H:%M} R-ONE 자료 꼴 · 건축물대장 전유부 표본"]
    base = "https://www.reb.or.kr/r-one/openapi"
    with httpx.Client(timeout=40, follow_redirects=True) as c:
        out.append("\n# R-ONE 「임대동향」 표 이름(연도 빼고 모음)")
        try:
            time.sleep(GAP)
            rows, _ = first_rows(
                c.get(
                    f"{base}/SttsApiTbl.do",
                    params={"KEY": rone, "Type": "json", "pIndex": 1, "pSize": 1000},
                ).json()
            )
            names: dict[str, str] = {}
            for x in rows:
                nm = str(x.get("STATBL_NM", ""))
                if "임대동향" in nm or "공실" in nm or "상가" in nm:
                    names[nm] = (
                        f"{x.get('STATBL_ID')} | {x.get('DTACYCLE_CD')} | {x.get('DATA_START_YY')}~{x.get('DATA_END_YY')}"
                    )
            for nm in sorted(names):
                if "(20" not in nm or "2026" in nm or "2024년" in nm:
                    out.append(f"   {names[nm]} | {nm}")
        except Exception as e:  # noqa: BLE001
            out.append(f"표 목록 실패: {type(e).__name__}")
        for tid, cyc, label in (
            ("T263433143798468", "QY", "소규모 상가 수익률"),
            ("T245503133561624", "MM", "오피스텔 수익률"),
            ("A_2024_00156", "MM", "전월세 전환율 아파트"),
        ):
            out.append(f"\n# R-ONE {label} ({tid})")
            call(
                c,
                out,
                "항목",
                f"{base}/SttsApiTblItm.do",
                {"KEY": rone, "Type": "json", "pIndex": 1, "pSize": 300, "STATBL_ID": tid},
                sec,
            )
            rows = call(c, out, "자료", f"{base}/SttsApiTblData.do",
                        {"KEY": rone, "Type": "json", "pIndex": 1, "pSize": 300, "STATBL_ID": tid, "DTACYCLE_CD": cyc}, sec)  # fmt: skip
            if rows:
                keys = [
                    k
                    for k in rows[0]
                    if k.endswith("_NM") or k in ("WRTTIME_IDTFR_ID", "DTA_VAL", "UI_NM")
                ]
                times = sorted({str(r.get("WRTTIME_IDTFR_ID")) for r in rows})
                out.append(f"   시점: {times[:3]} … {times[-3:]} ({len(times)}개)")
                for r in rows[:25]:
                    out.append("   " + " | ".join(str(r.get(k)) for k in keys))

        out.append("\n# 건축물대장 전유부 · 전유공용면적 · 기본개요")
        with connect() as conn:
            its = conn.execute(
                """select usage_name, region_code, lot_no, building_desc from core.items
                   where status_code = '01' and length(region_code) = 10 and lot_no ~ '^[0-9]+(-[0-9]+)?$'
                     and usage_name in ('아파트', '다세대') and sale_date >= current_date
                   order by usage_name, item_id limit 400"""
            ).fetchall()
        seen: set[str] = set()
        for usage, code, lot, desc in its:
            if usage in seen:
                continue
            seen.add(usage)
            plat, bun, ji = parse_jibun(lot) or ("0", "", "")
            out.append(f"\n## {usage} · {code} {lot} · {str(desc)[:60]}")
            p0 = {"serviceKey": key, "sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": plat, "bun": bun, "ji": ji,
                  "numOfRows": 5, "pageNo": 1, "_type": "json"}  # fmt: skip
            hub = "https://apis.data.go.kr/1613000/BldRgstHubService"
            call(c, out, "기본개요", f"{hub}/getBrBasisOulnInfo", p0, sec)
            ex = call(c, out, "전유부", f"{hub}/getBrExposInfo", p0, sec)
            call(c, out, "전유공용면적", f"{hub}/getBrExposPubuseAreaInfo", p0, sec)
            if ex:
                dong, ho = ex[0].get("dongNm"), ex[0].get("hoNm")
                out.append(f"   → 동 · 호로 좁혀 보기: dongNm={dong} hoNm={ho}")
                call(
                    c,
                    out,
                    "전유부(동·호)",
                    f"{hub}/getBrExposInfo",
                    {**p0, "dongNm": dong, "hoNm": ho},
                    sec,
                )
                call(
                    c,
                    out,
                    "전유공용면적(동·호)",
                    f"{hub}/getBrExposPubuseAreaInfo",
                    {**p0, "dongNm": dong, "hoNm": ho},
                    sec,
                )
    log = LOG.with_name("probe_more.log")
    log.parent.mkdir(exist_ok=True)
    log.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"끝: {log}")


def units() -> None:
    """건축물대장 전유공용면적을 「호」로 좁혀 받으면 물건의 호실과 맞는지(11/15) — 물건 40건. logs/probe_units.log"""
    import re
    from urllib.parse import unquote

    from aucs_rules.building import parse_jibun

    from aucs_workers.db import connect

    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    hub = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"
    with connect() as conn:
        its = conn.execute(
            """select usage_name, region_code, lot_no, building_desc, building_area_m2 from core.items
               where status_code = '01' and length(region_code) = 10 and lot_no ~ '^[0-9]+(-[0-9]+)?$'
                 and building_desc ~ '[0-9]+호' and sale_date >= current_date
                 and usage_name in ('아파트', '다세대', '오피스텔', '근린시설', '연립주택,다세대,빌라', '상가,오피스텔,근린시설')
               order by md5(item_id) limit 40"""
        ).fetchall()
    out = [f"=== {datetime.now():%Y-%m-%d %H:%M} 전유공용면적 — 호로 좁혀 받기 {len(its)}건"]
    ok = 0
    with httpx.Client(timeout=40) as c:
        for usage, code, lot, desc, area in its:
            plat, bun, ji = parse_jibun(lot) or ("0", "", "")
            ho = re.search(r"([A-Za-z]?\d+)\s*호", desc or "")
            dong = re.search(r"(\d+|[가-힣A-Za-z])동\s", desc or "")
            under = bool(re.search(r"지층|지하|비\d", desc or ""))
            rows: list[dict[str, Any]] = []
            for name in [ho.group(1), ("B" + ho.group(1)) if under else None] if ho else []:
                if not name or rows:
                    continue
                time.sleep(0.3)
                try:
                    d = c.get(hub, params={"serviceKey": key, "sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": plat,
                                           "bun": bun, "ji": ji, "hoNm": name, "numOfRows": 100, "pageNo": 1, "_type": "json"}).json()  # fmt: skip
                    rows, _ = first_rows(d)
                except Exception as e:  # noqa: BLE001
                    out.append(f"   오류 {type(e).__name__}")
            rows = [r for r in rows if "hoNm" in r]
            dongs = sorted({str(r.get("dongNm") or "").strip() for r in rows})
            own = [r for r in rows if r.get("exposPubuseGbCdNm") == "전유"]
            if dong and len(dongs) > 1:
                own = [r for r in own if dong.group(1) in str(r.get("dongNm") or "")]
            own_area = sum(float(r.get("area") or 0) for r in own)
            hit = bool(own) and area and abs(own_area - float(area)) <= 1.0
            ok += bool(hit)
            out.append(f"{'○' if hit else '×'} {usage} | {str(desc)[:40]} | 우리 면적 {area} | 호 {ho.group(1) if ho else None} 동 {dong.group(1) if dong else None}"
                       f" | 받은 줄 {len(rows)} 동 {dongs[:4]} | 전유 {[(r.get('mainPurpsCdNm'), r.get('etcPurps'), r.get('area'), r.get('hoNm')) for r in own[:3]]}")  # fmt: skip
    out.insert(1, f"전유면적이 우리 면적과 맞음(±1㎡): {ok}/{len(its)}")
    log = LOG.with_name("probe_units.log")
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
    {"--redev": redev, "--more": more, "--units": units}.get(sys.argv[-1], main)()
