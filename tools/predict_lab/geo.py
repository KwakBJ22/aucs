"""좌표 → 지번(브이월드 역지오코딩). 강사 자료의 xCordi · yCordi 는 KATEC(TM128, 네이버 지도 좌표계) 미터 값이다.

- 한 번 물은 좌표는 geo_cache.json 에 저장해 다시 안 묻는다(못 찾은 좌표도).
- 하루 호출 한도를 지킨다(캐시 파일에 날짜별 호출 수를 적음). 한도 · 인증 오류면 받은 데까지 저장하고 멈춘다.
- 키: 환경 변수 VWORLD_API_KEY 또는 저장소 .env (읽기만, 값은 출력하지 않음). 법원 사이트와 무관.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from market import parse_addr_jibun
from paths import GEO_CACHE

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
URL = "https://api.vworld.kr/req/address"
DAILY_LIMIT = int(os.environ.get("VWORLD_DAILY_LIMIT", "30000"))
GAP_SEC = 0.05
KATEC_PROJ = (
    "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 "
    "+ellps=bessel +towgs84=-146.43,507.89,681.46 +units=m +no_defs"
)


class ApiError(Exception):
    """인증 · 한도 등 — 더 물어도 소용없는 오류."""


class Transient(Exception):
    """서버 일시 오류(5xx) · 연결 끊김 — 잠깐 뒤 다시 시도."""


def coord_key(x: float, y: float) -> str:
    return f"{int(round(x))},{int(round(y))}"


def katec_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """KATEC 미터 → (경도, 위도)."""
    from pyproj import Transformer

    global _TF
    if _TF is None:
        _TF = Transformer.from_crs(KATEC_PROJ, "EPSG:4326", always_xy=True)
    return _TF.transform(x, y)


_TF = None


def load_cache(path: Path = GEO_CACHE) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"usage": {}, "points": {}}


def save_cache(cache: dict, path: Path = GEO_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def lookup(cache: dict, x: float | None, y: float | None) -> tuple[str, str] | None:
    """캐시에서 (법정동, 지번). 못 찾았거나 아직 안 물었으면 None(둘은 stored 로 구분)."""
    if x is None or y is None:
        return None
    v = cache["points"].get(coord_key(x, y))
    if not v or v.get("none"):
        return None
    return v["umd"], v["jibun"]


def parse_result(res: dict) -> tuple[str, str] | None:
    """브이월드 getAddress 응답의 한 줄 → (법정동, 지번). 지번 끝의 지목 글자(전 · 답 …)는 뗀다."""
    text = ((res.get("result") or [{}])[0]).get("text") or ""
    umd, jibun = parse_addr_jibun(text)
    return (umd, jibun) if umd and jibun else None


def reverse_vworld(client, key: str, domain: str, lon: float, lat: float) -> tuple[str, str] | None:
    """좌표 → (법정동, 지번). 주소 없음은 None, 인증 · 한도 오류는 ApiError."""
    r = client.get(
        URL,
        params={"service": "address", "request": "getAddress", "version": "2.0", "crs": "epsg:4326",
                "point": f"{lon},{lat}", "type": "parcel", "format": "json", "key": key, "domain": domain},
    )  # fmt: skip
    if r.status_code >= 500:
        raise Transient(f"HTTP {r.status_code}")
    try:
        res = r.json()["response"]
    except (ValueError, KeyError) as e:
        raise ApiError(f"HTTP {r.status_code} · {r.text[:120]}") from e
    if res.get("status") == "OK":
        return parse_result(res)
    if res.get("status") == "NOT_FOUND":
        return None
    raise ApiError(str(res.get("error") or res)[:200])


def fill_cache(
    coords: list[tuple[float, float]],
    cache: dict,
    fetch: Callable[[float, float], tuple[str, str] | None],
    *,
    today: date,
    daily_limit: int = DAILY_LIMIT,
    save: Callable[[dict], None] | None = None,
    gap: float = 0.0,
) -> dict:
    """아직 안 물은 좌표만 fetch 로 묻고 cache 에 넣는다. fetch(x, y) 는 KATEC 좌표를 받는다.
    하루 한도에 닿거나 ApiError 면 멈춘다. 돌려주는 값: 물은 수 · 건너뛴(이미 있는) 수 · 남은 수 · 멈춘 까닭."""
    usage = cache.setdefault("usage", {})
    used = int(usage.get(today.isoformat(), 0))
    pts = cache.setdefault("points", {})
    asked = skipped = 0
    stop = ""
    todo = []
    seen = set()
    for x, y in coords:
        k = coord_key(x, y)
        if k in pts:
            skipped += 1
        elif k not in seen:
            seen.add(k)
            todo.append((x, y))
    done_n = 0
    for x, y in todo:
        if used >= daily_limit:
            stop = "하루 한도"
            break
        if gap:
            time.sleep(gap)
        try:
            hit = fetch(x, y)
        except ApiError as e:
            stop = f"오류: {e}"
            break
        used += 1
        asked += 1
        done_n += 1
        pts[coord_key(x, y)] = {"umd": hit[0], "jibun": hit[1]} if hit else {"none": True}
        usage[today.isoformat()] = used
        if save and asked % 500 == 0:
            save(cache)
    usage[today.isoformat()] = used
    if save:
        save(cache)
    return {
        "물은 수": asked,
        "이미 있어 건너뜀": skipped,
        "남은 수": len(todo) - done_n,
        "멈춤": stop,
    }


def _vworld_credentials() -> tuple[str, str]:
    key = os.environ.get("VWORLD_API_KEY", "")
    domain = os.environ.get("VWORLD_DOMAIN", "")
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
        if not key and (m := re.search(r"^VWORLD_API_KEY=(.+)$", text, re.M)):
            key = m.group(1)
        if not domain and (m := re.search(r"^VWORLD_DOMAIN=(.+)$", text, re.M)):
            domain = m.group(1)
    key = key.strip().strip("\"'")
    if not key:
        raise SystemExit("VWORLD_API_KEY 가 없습니다(.env)")
    return key, (domain.strip().strip("\"'") or "https://aucs.co.kr")


def geocode_missing(coords: list[tuple[float, float]], today: date | None = None) -> dict:
    """캐시에 없는 좌표를 브이월드에 묻는다(진짜 호출). build_table 이 부른다."""
    import httpx

    today = today or date.today()
    cache = load_cache()
    key, domain = _vworld_credentials()
    with httpx.Client(timeout=30) as client:

        def fetch(x: float, y: float):
            lon, lat = katec_to_wgs84(x, y)
            for attempt in range(
                4
            ):  # 연결이 잠깐 끊기면 다시 시도, 계속 안 되면 멈추고 받은 데까지 저장
                try:
                    return reverse_vworld(client, key, domain, lon, lat)
                except (httpx.HTTPError, Transient) as e:
                    if attempt == 3:
                        raise ApiError(f"연결 · 서버 오류 {type(e).__name__} {e}") from e
                    time.sleep(3 * (attempt + 1))

        return fill_cache(coords, cache, fetch, today=today, save=save_cache, gap=GAP_SEC)
