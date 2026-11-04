"""법정동 표 채우기 — 행정안전부 「법정동코드」(data.go.kr StanReginCd, 활용신청 필요).

서울·경기·인천 법정동(읍·면·동)을 받아 ref.regions 에 없는 것만 더함(있는 줄은 건드리지 않음).
빠진 동(예: 2026년 새로 생긴 화성 동탄구 오산동)이 있으면 지역 코드 바로잡기·건축물대장·시세가 이웃 동으로 붙던 것을 막음.

    uv run python -m aucs_workers.collectors.regions
"""

import os
from typing import Any
from urllib.parse import unquote

import httpx

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

URL = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
SIDO = ["서울특별시", "경기도", "인천광역시"]  # 인천 11/4
ROWS = 1000


def pick(r: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if r.get(k) not in (None, ""):
            return r[k]
    return None


def to_row(r: dict[str, Any]) -> dict[str, str] | None:
    """API 한 줄 → ref.regions 한 줄(읍·면·동만, 리는 뺌). 없어진 코드도 뺌. (순수 함수)"""
    code = str(pick(r, "region_cd", "regionCd") or "")
    name = str(pick(r, "locatadd_nm", "locataddNm") or "").split()
    if len(code) != 10 or code.endswith("00000") or code[8:] != "00" or len(name) < 3:
        return None  # 시도·시군구·리 줄
    sido, dong = name[0], name[-1]
    return {
        "region_code": code,
        "sido": sido,
        "sigungu": " ".join(name[1:-1]),
        "eupmyeondong": dong,
        "sigungu_code": code[:5],
        "full_name": " ".join(name),
    }


def rows_of(d: Any) -> list[dict[str, Any]]:
    """응답 모양: {"StanReginCd": [{"head": [...]}, {"row": [...]}]}"""
    for part in (d or {}).get("StanReginCd", []) or []:
        if isinstance(part, dict) and "row" in part:
            return list(part["row"] or [])
    return []


def main() -> None:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    found: dict[str, dict[str, str]] = {}
    with httpx.Client(timeout=30) as client:
        for sido in SIDO:
            page = 1
            while True:
                res = client.get(URL, params={"ServiceKey": key, "type": "json", "pageNo": page,
                                              "numOfRows": ROWS, "flag": "Y", "locatadd_nm": sido})  # fmt: skip
                if "json" not in res.headers.get(
                    "content-type", ""
                ) and not res.text.lstrip().startswith("{"):
                    raise SystemExit(
                        f"[멈춤] 법정동코드 API 응답이 JSON 이 아님 — 활용신청을 확인하세요: {res.text[:200]}"
                    )
                got = rows_of(res.json())
                for r in got:
                    x = to_row(r)
                    if x:
                        found[x["region_code"]] = x
                if len(got) < ROWS:
                    break
                page += 1
    with connect() as conn, run(conn, "regions", "법정동 표") as job:
        have = {r[0] for r in conn.execute("select region_code from ref.regions").fetchall()}
        new = [x for c, x in found.items() if c not in have]
        # 시군구 줄(…00000)도 없으면 더함 — 처음 들어오는 시도(인천, 11/4)는 시군구 줄이 없어 지역 목록·실거래 수집에서 빠졌음
        sgg = {x["sigungu_code"]: x for x in found.values()}
        new_sgg = [
            {"region_code": c + "00000", "sido": x["sido"], "sigungu": x["sigungu"],
             "sigungu_code": c, "full_name": f'{x["sido"]} {x["sigungu"]}'}
            for c, x in sgg.items() if c + "00000" not in have
        ]  # fmt: skip
        with conn.cursor() as cur:
            cur.executemany(
                """insert into ref.regions (region_code, level, sido, sigungu, eupmyeondong, sigungu_code, full_name)
                   values (%(region_code)s, 'sigungu', %(sido)s, %(sigungu)s, null, %(sigungu_code)s, %(full_name)s)
                   on conflict (region_code) do nothing""",
                new_sgg,
            )
            cur.executemany(
                """insert into ref.regions (region_code, level, sido, sigungu, eupmyeondong, sigungu_code, full_name)
                   values (%(region_code)s, 'dong', %(sido)s, %(sigungu)s, %(eupmyeondong)s, %(sigungu_code)s, %(full_name)s)
                   on conflict (region_code) do nothing""",
                new,
            )
        conn.commit()
        job.count = len(new)
        print(
            f"받은 동 {len(found):,} · 새로 더한 동 {len(new):,} · 새로 더한 시군구 {len(new_sgg):,}"
        )
        for x in new[:20]:
            print("  +", x["full_name"], x["region_code"])


if __name__ == "__main__":
    main()
