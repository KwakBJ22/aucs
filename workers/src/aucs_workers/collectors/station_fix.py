"""역 좌표 바로잡기(11/15 대표님 — 판교역이 수원 영통 옆으로 나옴).

원인: ref.stations 는 공공데이터 「전국도시철도역사정보」를 그대로 옮긴 것인데, 운영기관이 적어 낸 위도 · 경도가
틀린 역이 있음(판교 · 동천(신분당선) · 연신내(6호선) · 발곡 · 오목천 · 구리(경의중앙선) · 교대(동해선) …).
같은 자료의 주소(지번 · 도로명)는 맞으므로, 주소를 브이월드 좌표로 바꿔 견주고 크게 어긋난 역만 주소 좌표로 고침.

    cd D:\Auction\auction-platform\workers
    uv run python -m aucs_workers.collectors.station_fix          # 견주고 고침(5분쯤)
    uv run python -m aucs_workers.collectors.station_fix --dry    # 고치지 않고 보여 주기만

- 주소는 db/seed/station_address.csv(경매레이더 「철도역」 표에서 뽑은 것 — 역 이름 · 노선 · 운영기관으로 맞춤).
- 고치는 때: 지금 좌표가 주소 좌표에서 1.5km 넘게 떨어져 있고, ① 지번 · 도로명 주소 좌표가 서로 맞거나(700m 안)
  ② 주소 좌표 700m 안에 이름이 같은 다른 노선 역이 있거나 ③ 3km 안에 있으면 그 역 좌표로(같은 역)
  ④ 적힌 그대로 찾은 주소 좌표가 같은 노선 앞뒤 역 사이에 놓이고 지금 좌표는 안 놓일 때. 그 밖은 「확인 필요」로 적기만 함.
- 브이월드는 주소를 못 찾으면 길 가운데 같은 거친 좌표로도 답함(「○○대로 지하 1280」들이 한 점) — 그런 좌표로는 ④ 를 안 씀.
- 결과는 화면과 logs/station_fix.log 에. 다시 돌려도 됨(이미 고친 역은 그대로). 키: .env 의 VWORLD_API_KEY.
"""

import argparse
import csv
import math
import os
import re
import time
from datetime import datetime
from typing import Any

import httpx

from aucs_workers.collectors.redev_geo import ApiError, geocode
from aucs_workers.db import ROOT, connect
from aucs_workers.jobs.runlog import run

SEED = ROOT / "db" / "seed" / "station_address.csv"
LOG = ROOT / "logs" / "station_fix.log"
GAP = 0.2
TWIN_M = 3000  # 주소 좌표가 이름 같은 다른 노선 역에서 이만큼 안이면 같은 역
NEAR_M = 700  # 주소 좌표와 이만큼 안이면 같은 자리로 봄(역무실 주소가 승강장과 조금 다름)
FAR_M = 1500  # 이보다 멀면 좌표가 틀린 것

Pt = tuple[float, float]  # (경도, 위도)
Cand = tuple[Pt, bool]  # (좌표, 적힌 그대로 찾았나)
_PAREN = re.compile(r"\([^)]*\)?")
# 맨 뒤의 「○○로(길)」 + 건물번호 — 「건원대로 34번길 32-29」는 「건원대로 34번길」 · 「32-29」
_ROAD = re.compile(r"^(.*(?:로|길))\s*(지하)?\s*(\d+(?:-\d+)?)")
_LOT = re.compile(r"^(.*?(?:동|리|가|읍|면))\s*(산)?\s*(\d+(?:-\d+)?)")


def dist_m(a: Pt, b: Pt) -> float:
    """두 점 사이(m)."""
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(h))


def base_name(name: str) -> str:
    """「판교 (판교테크노밸리)」「동천역」 → 「판교」「동천」."""
    n = _PAREN.sub("", name).strip()
    return n[:-1] if n.endswith("역") and len(n) > 2 else n


def road_forms(addr: str) -> list[str]:
    """도로명주소 → 물어볼 꼴들(「지하」를 넣은 것 · 뺀 것). 건물번호까지만."""
    m = _ROAD.match(_PAREN.sub(" ", addr.replace("_x000D_", " ")).strip())
    if not m:
        return []
    head, under, no = m.groups()
    out = [f"{head} 지하 {no}"] if under else []
    return [*out, f"{head} {no}"]


def lot_form(addr: str) -> str | None:
    """지번주소 → 지번까지만(뒤의 「○○역(3호선)」 · 「일원」은 뗌)."""
    m = _LOT.match(_PAREN.sub(" ", addr.replace("_x000D_", " ")).strip())
    if not m:
        return None
    head, san, no = m.groups()
    return f"{head} {'산 ' if san else ''}{no}"


def between(p: Pt, sides: list[Pt]) -> float | None:
    """같은 노선 앞뒤 역 사이에 놓이나 → 돌아가는 거리(m, 작을수록 자연스러움). 안 놓이면 None."""
    if len(sides) == 2:
        extra = dist_m(p, sides[0]) + dist_m(p, sides[1]) - dist_m(sides[0], sides[1])
        return extra if extra <= 0.5 * dist_m(sides[0], sides[1]) + 500 else None
    if len(sides) == 1:  # 끝 역
        d = dist_m(p, sides[0])
        return d if d <= 5000 else None
    return None


def decide(
    old: Pt, road: Cand | None, lot: Cand | None, twins: list[Pt], sides: list[Pt]
) -> tuple[str, Pt | None]:
    """→ (ok · none · near · fix · check, 새 좌표). twins: 이름이 같은 다른 노선 역 · sides: 같은 노선 앞뒤 역."""
    cand = [c for c in (road, lot) if c]
    if not cand:
        return "none", None
    d = min(dist_m(old, p) for p, _ in cand)
    if d <= NEAR_M:
        return "ok", None
    if d <= FAR_M:
        return "near", None
    best = sorted(cand, key=lambda c: not c[1])[0][0]  # 적힌 그대로 찾은 것 먼저
    if road and lot and dist_m(road[0], lot[0]) <= NEAR_M:
        return "fix", best
    for p, _ in cand:
        if any(dist_m(p, t) <= NEAR_M for t in twins):
            return "fix", p
    for t in twins:
        if dist_m(old, t) > FAR_M and any(dist_m(p, t) <= TWIN_M for p, _ in cand):
            return "fix", t
    if between(old, sides) is None:
        fit = sorted((x, p) for p, exact in cand if exact and (x := between(p, sides)) is not None)
        if fit:
            return "fix", fit[0][1]
    return "check", best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="고치지 않고 보여 주기만")
    a = ap.parse_args()
    key = os.getenv("VWORLD_API_KEY", "").strip().strip("\"'")
    domain = os.getenv("VWORLD_DOMAIN", "https://aucs.co.kr").strip()
    if not key:
        raise SystemExit("VWORLD_API_KEY 가 비어 있습니다 (.env)")
    with open(SEED, encoding="utf-8", newline="") as f:
        seed = {(r["name_ko"], r["line_name"], r["operator"]): r for r in csv.DictReader(f)}
    lines: list[str] = []
    n: dict[str, int] = {}
    cache: dict[tuple[str, str], Cand | None] = {}
    # 같은 노선 앞뒤 역(주소 자료가 운영기관 · 노선 · 역번호 순)
    order = list(seed)
    sides_of: dict[tuple[str, str, str], list[tuple[str, str, str]]] = {}
    for i, k in enumerate(order):
        sides_of[k] = [
            o for o in (order[i - 1] if i else None, order[i + 1] if i + 1 < len(order) else None)
            if o and o[1:] == k[1:]
        ]  # fmt: skip
    with connect() as conn, run(conn, "station_fix", "역 좌표 바로잡기") as job:
        rows: list[tuple[Any, ...]] = conn.execute(
            """select station_id, name_ko, line_name, operator,
                      st_x(geom::geometry), st_y(geom::geometry) from ref.stations order by station_id"""
        ).fetchall()
        by_base: dict[str, list[tuple[int, Pt]]] = {}
        now_at: dict[tuple[str, str, str], Pt] = {}  # 지금 좌표(이번에 고친 것 반영)
        for sid, name, line, op, x, y in rows:
            by_base.setdefault(base_name(name), []).append((sid, (x, y)))
            now_at[(name, line, op)] = (x, y)
        print(
            f"[시작] 역 {len(rows):,}곳 · 주소 {len(seed):,}줄"
            + (" · 보여 주기만" if a.dry else "")
        )
        with httpx.Client(timeout=30) as client:

            def ask(addr: str, kind: str) -> Cand | None:
                """적힌 그대로 먼저, 없으면 비슷한 주소로(거친 좌표)."""
                if (addr, kind) not in cache:
                    time.sleep(GAP)
                    pt = geocode(client, key, domain, addr, kind, refine=False)
                    if pt is None:
                        time.sleep(GAP)
                        rough = geocode(client, key, domain, addr, kind)
                        cache[(addr, kind)] = (rough, False) if rough else None
                    else:
                        cache[(addr, kind)] = (pt, True)
                return cache[(addr, kind)]

            for i, (sid, name, line, op, x, y) in enumerate(rows, 1):
                s = seed.get((name, line, op))
                old: Pt = (x, y)
                road = lot = None
                try:
                    if s:
                        for form in road_forms(s["road_address"] or ""):
                            road = ask(form, "road")
                            if road:
                                break
                        if not road or dist_m(old, road[0]) > NEAR_M:  # 맞으면 지번은 안 물음
                            # 지번 칸이 비고 도로명 칸에 지번이 적힌 역도 있음
                            form2 = lot_form(s["lot_address"] or "") or lot_form(
                                s["road_address"] or ""
                            )
                            lot = ask(form2, "parcel") if form2 else None
                except (ApiError, httpx.HTTPError) as e:
                    conn.commit()
                    print(
                        f"\n[멈춤] {name}({line}): {e}\n  키 · 하루 한도를 확인하세요. 고친 데까지 저장했어요."
                    )
                    raise SystemExit(1) from e
                twins = [p for t, p in by_base.get(base_name(name), []) if t != sid]
                sides = [now_at[k] for k in sides_of.get((name, line, op), []) if k in now_at]
                what, new = decide(old, road, lot, twins, sides)
                n[what] = n.get(what, 0) + 1
                if what in ("fix", "check") and new:
                    lines.append(
                        f"{'고침' if what == 'fix' else '확인 필요'} · {name}({line} · {op}) "
                        f"{y:.5f},{x:.5f} → {new[1]:.5f},{new[0]:.5f} · {dist_m(old, new) / 1000:.1f}km"
                        f" · {(s or {}).get('road_address') or (s or {}).get('lot_address') or ''}"
                        + "".join(
                            f" · {w} {c[0][1]:.5f},{c[0][0]:.5f}{'' if c[1] else '(거침)'}"
                            for w, c in (("도로명", road), ("지번", lot))
                            if c
                        )
                    )
                    print("  " + lines[-1], flush=True)
                if what == "fix" and new and not a.dry:
                    conn.execute(
                        """update ref.stations
                           set geom = st_setsrid(st_makepoint(%s::float8, %s::float8), 4326)::geography
                           where station_id = %s""",
                        (new[0], new[1], sid),
                    )
                    job.count += 1
                    now_at[(name, line, op)] = new
                if i % 200 == 0:
                    conn.commit()
                    print(f"  {i:,}/{len(rows):,}", flush=True)
        msg = (
            f"역 {len(rows):,}곳 · 맞음 {n.get('ok', 0):,} · 고침 {n.get('fix', 0)} · 확인 필요 {n.get('check', 0)}"
            f" · 조금 다름 {n.get('near', 0)} · 주소로 못 찾음 {n.get('none', 0)}"
            + (" · 보여 주기만" if a.dry else "")
        )
        conn.execute("update ops.job_runs set message = %s where run_id = %s", (msg, job.run_id))
        conn.commit()
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"── {datetime.now():%Y-%m-%d %H:%M} {msg}\n" + "".join(x + "\n" for x in lines))
    print("끝: " + msg)


if __name__ == "__main__":
    main()
