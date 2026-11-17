"""군포시(41410) 토지 매매 실거래가 늘 0줄인 까닭 표본(11/18) — DB 에 안 넣음, 결과는 logs/requests.log.

같은 달에 군포시 토지 · 군포시 아파트 · 이웃 의왕시(41430) 토지를 불러 totalCount 를 견줌. 4번만 부름(하루 한도 1,000).
"""

import json
import os
from urllib.parse import unquote

import httpx
import xmltodict

import aucs_workers.db  # noqa: F401 — 저장소 맨 위 .env 를 읽음(키)

BASE = "https://apis.data.go.kr/1613000"
CALLS = [
    ("군포 토지 2026-10", "RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade", "41410", "202610"),
    ("군포 토지 2026-09", "RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade", "41410", "202609"),
    ("군포 아파트 2026-10", "RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade", "41410", "202610"),
    ("의왕 토지 2026-10", "RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade", "41430", "202610"),
]


def main() -> None:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    with httpx.Client(timeout=30) as c:
        for name, path, lawd, ym in CALLS:
            r = c.get(
                f"{BASE}/{path}",
                params={
                    "serviceKey": key,
                    "LAWD_CD": lawd,
                    "DEAL_YMD": ym,
                    "numOfRows": 3,
                    "pageNo": 1,
                },
            )
            body = (r.text or "").strip()
            try:
                d = xmltodict.parse(body) if body.startswith("<") else json.loads(body)
                h = (d.get("response") or {}).get("header") or {}
                b = (d.get("response") or {}).get("body") or {}
                print(
                    f"{name}: http {r.status_code} · 코드 {h.get('resultCode')} {h.get('resultMsg')} · 건수 {b.get('totalCount')}"
                )
                if "OpenAPI_ServiceResponse" in d:
                    print(f"  오류: {d['OpenAPI_ServiceResponse'].get('cmmMsgHeader')}")
            except Exception as e:  # noqa: BLE001 — 표본이라 그대로 찍음
                print(f"{name}: http {r.status_code} · 읽기 실패 {e} · {body[:200]}")


if __name__ == "__main__":
    main()
