"""역 좌표를 공식 자료로 맞추기(11/15 대표님 — 공공데이터를 직접 받아 견줘 보라).

국가철도공단 레일포털(data.kric.go.kr)의 「표준데이터 역사정보(전체 기관)」 파일(공공데이터포털
「전국도시철도역사정보표준데이터」의 원본, 해마다 갱신)을 받아 ref.stations 의 좌표를 그 값으로 맞춤.
10/17 에 넣은 좌표는 강사에게 받은 파일(「전국 도시광역철도 역사 역사정보_20260701.xlsx」)에서 온 것으로,
판교 · 동천 · 6호선 등 56곳이 틀려 있었음. 공식 파일은 그 역들이 모두 맞음(11/15 견줌).

    cd D:\Auction\auction-platform\workers
    uv run python -m aucs_workers.collectors.station_official          # 받아서 맞춤
    uv run python -m aucs_workers.collectors.station_official --dry    # 고치지 않고 보여 주기만
    uv run python -m aucs_workers.collectors.station_official --file D:\내려받은.xlsx   # 받아 둔 파일로

- 맞추는 법: 이름(괄호 · 「역」 뗌)이 같은 공식 역 가운데 3km 안에서 노선이 같은 것 → 가장 가까운 것.
  3km 넘게 떨어져 있으면 노선 · 지역까지 맞는 역이 하나뿐일 때만 옮기고, 아니면 「확인 필요」로 적기만 함.
- 공식 파일에도 옆 역과 같은 좌표로 적힌 역이 있음(마곡 = 발산 · 신용산 = 이촌) — 그런 역은 건드리지 않음.
- 공식 파일에 없는 역(GTX-A 등)은 그대로 둠. 이름 · 노선 이름은 바꾸지 않고 좌표만 바꿈.
- 받은 파일은 logs/station_official.xlsx, 결과는 logs/station_official.log. 관리자 「다시 돌리기」로도 돌림.
"""

import argparse
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from aucs_workers.collectors.station_fix import Pt, base_name, dist_m
from aucs_workers.db import ROOT, connect
from aucs_workers.jobs.runlog import run

URL = "https://data.kric.go.kr/rips/dataset/download.file"
PARAMS = {"type": "filedata", "id": "32", "operation": "1"}
KEEP = ROOT / "logs" / "station_official.xlsx"
LOG = ROOT / "logs" / "station_official.log"
SAME_M = 30  # 이만큼 안이면 같은 좌표
NEAR_M = 3000  # 이만큼 안이면 이름만 같아도 같은 역으로 봄
DUP_M = 150  # 공식 자료에서 같은 노선 다른 역과 이만큼 안이면 베껴 적힌 좌표
HEAD = {
    "name": ("역사명", "역명(한글)"),
    "line": ("노선명", "운영노선"),
    "lat": ("역위도", "역 위치(위도)"),
    "lon": ("역경도", "역 위치(경도)"),
    "op": ("운영기관명", "철도운영기관명"),
}
CITIES = ("서울", "부산", "대구", "대전", "광주", "인천")
WORDS = ("신분당", "분당", "수인", "경의중앙", "경춘", "경강", "동해", "공항", "서해", "우이", "의정부",
         "에버", "용인", "김포", "신림", "진접", "대경", "자기부상", "부산김해", "GTX")  # fmt: skip
ALIAS = {"경부": "1호선", "경인": "1호선", "경원": "1호선", "장항": "1호선", "안산과천": "4호선",
         "과천": "4호선", "안산": "4호선", "일산": "3호선", "용인": "에버"}  # fmt: skip


def read_xlsx(data: bytes) -> list[dict[str, str]]:
    """xlsx 첫 시트 → 줄마다 {머리글: 값}(글자 그대로). 따로 깔 것 없이 zip · xml 만 읽음."""
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    strs: list[str] = []
    if "xl/sharedStrings.xml" in names:
        for m in re.finditer(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S):
            strs.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", m.group(1), re.S)))
    sheet = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))[0]
    rows: list[dict[str, str]] = []
    for rm in re.finditer(r"<row[^>]*>(.*?)</row>", z.read(sheet).decode(), re.S):
        row: dict[str, str] = {}
        for c in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', rm.group(1), re.S):
            col, attr, body = c.groups()
            if not body:
                continue
            v = re.search(r"<v>(.*?)</v>", body, re.S) or re.search(
                r"<t[^>]*>(.*?)</t>", body, re.S
            )
            if v:
                row[col] = strs[int(v.group(1))] if 't="s"' in attr else v.group(1)
        rows.append(row)
    if not rows:
        return []
    head = {col: h.strip() for col, h in rows[0].items()}
    return [{head[c]: v for c, v in r.items() if c in head} for r in rows[1:]]


def stations(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """공식 파일 줄 → [{name, line, op, pt}] (좌표 없는 줄은 뺌)."""
    out = []
    for r in rows:
        g = {k: next((r[h] for h in hs if r.get(h)), "") for k, hs in HEAD.items()}
        try:
            pt = (float(g["lon"]), float(g["lat"]))
        except ValueError:
            continue
        if g["name"] and 124 < pt[0] < 132 and 33 < pt[1] < 39:
            out.append(
                {"name": g["name"].strip(), "line": g["line"].strip(), "op": g["op"], "pt": pt}
            )
    return out


def line_key(line: str, op: str = "") -> tuple[str, str]:
    """노선 이름 → (노선 낱말, 지역). 「경부선」 = 「1호선」, 「인천지하철 1호선」 = (「1호선」, 「인천」)."""
    s = line.replace(" ", "")
    city = next((c for c in CITIES if c in s or c in op), "")
    for k, v in ALIAS.items():
        if k in s:
            return v, city
    for w in WORDS:
        if w in s:
            return w, city
    m = re.search(r"(\d)호선", s)
    return (m.group(1) + "호선" if m else s), city


def same_line(a: tuple[str, str], b: tuple[str, str]) -> bool:
    return a[0] == b[0] and (a[1] == b[1] or not a[1] or not b[1])


def copied(off: list[dict[str, Any]]) -> set[int]:
    """공식 자료에서 같은 노선 다른 이름 역과 좌표가 같은 줄(베껴 적힌 것)."""
    bad: set[int] = set()
    for i, a in enumerate(off):
        for j in range(i + 1, len(off)):
            b = off[j]
            if (
                a["line"] == b["line"]
                and abs(a["pt"][1] - b["pt"][1]) < 0.003
                and base_name(a["name"]) != base_name(b["name"])
                and base_name(a["name"]) not in b["name"]
                and base_name(b["name"]) not in a["name"]
                and dist_m(a["pt"], b["pt"]) <= DUP_M
            ):
                bad |= {i, j}
    return bad


def pick(
    name: str,
    line: str,
    op: str,
    old: Pt,
    off: list[dict[str, Any]],
    by: dict[str, list[int]],
    bad: set[int],
) -> tuple[str, Pt | None]:
    """→ (same · move · far · check · dup · none, 새 좌표)."""
    ids = by.get(base_name(name), [])
    if not ids:
        return "none", None
    mine = line_key(line, op)
    ranked = sorted(
        ids,
        key=lambda i: (
            not same_line(mine, line_key(off[i]["line"], off[i]["op"])),
            dist_m(old, off[i]["pt"]),
        ),
    )
    near = [i for i in ranked if dist_m(old, off[i]["pt"]) <= NEAR_M]
    if near:
        i = near[0]
        if i in bad:
            return "dup", off[i]["pt"]
        return ("same" if dist_m(old, off[i]["pt"]) <= SAME_M else "move"), off[i]["pt"]
    sure = [i for i in ids if same_line(mine, line_key(off[i]["line"], off[i]["op"]))]
    if len(sure) == 1 and sure[0] not in bad:
        return "far", off[sure[0]]["pt"]
    return "check", off[ranked[0]]["pt"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="고치지 않고 보여 주기만")
    ap.add_argument("--file", help="받아 둔 xlsx(없으면 레일포털에서 받음)")
    a = ap.parse_args()
    if a.file:
        data = Path(a.file).read_bytes()
    else:
        r = httpx.get(URL, params=PARAMS, timeout=60, follow_redirects=True)
        r.raise_for_status()
        data = r.content
        KEEP.parent.mkdir(exist_ok=True)
        KEEP.write_bytes(data)
    off = stations(read_xlsx(data))
    if len(off) < 900:
        raise SystemExit(
            f"공식 파일에서 역을 {len(off)}곳만 읽음 — 파일 꼴이 바뀐 듯. 아무것도 고치지 않았어요."
        )
    by: dict[str, list[int]] = {}
    for i, o in enumerate(off):
        by.setdefault(base_name(o["name"]), []).append(i)
    bad = copied(off)
    lines: list[str] = []
    n: dict[str, int] = {}
    with connect() as conn, run(conn, "station_official", "역 좌표 공식 자료로 맞추기") as job:
        rows = conn.execute(
            """select station_id, name_ko, line_name, operator,
                      st_x(geom::geometry), st_y(geom::geometry) from ref.stations order by station_id"""
        ).fetchall()
        print(
            f"[시작] 우리 역 {len(rows):,}곳 · 공식 {len(off):,}곳"
            + (" · 보여 주기만" if a.dry else "")
        )
        for sid, name, line, op, x, y in rows:
            what, new = pick(name, line, op or "", (x, y), off, by, bad)
            n[what] = n.get(what, 0) + 1
            d = dist_m((x, y), new) if new else 0
            if what in ("far", "check", "dup") or (what == "move" and d > 300):
                word = {"move": "옮김", "far": "멀리 옮김", "check": "확인 필요",
                        "dup": "공식 자료가 옆 역과 같은 좌표 — 그대로 둠"}[what]  # fmt: skip
                assert new is not None
                lines.append(
                    f"{word} · {name}({line} · {op}) {y:.5f},{x:.5f} → {new[1]:.5f},{new[0]:.5f} · {d / 1000:.2f}km"
                )
                print("  " + lines[-1], flush=True)
            if what in ("move", "far") and new and not a.dry:
                conn.execute(
                    """update ref.stations
                       set geom = st_setsrid(st_makepoint(%s::float8, %s::float8), 4326)::geography
                       where station_id = %s""",
                    (new[0], new[1], sid),
                )
                job.count += 1
        msg = (
            f"우리 역 {len(rows):,}곳 · 공식 {len(off):,}곳 · 같음 {n.get('same', 0):,} · 옮김 {n.get('move', 0):,}"
            f" · 멀리 옮김 {n.get('far', 0)} · 확인 필요 {n.get('check', 0)} · 공식이 베낀 좌표 {n.get('dup', 0)}"
            f" · 공식에 없음 {n.get('none', 0)}" + (" · 보여 주기만" if a.dry else "")
        )
        conn.execute(
            "update ops.job_runs set message = %s where run_id = %s", (msg[:500], job.run_id)
        )
        conn.commit()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"── {datetime.now():%Y-%m-%d %H:%M} {msg}\n" + "".join(x + "\n" for x in lines))
    print("끝: " + msg)


if __name__ == "__main__":
    main()
