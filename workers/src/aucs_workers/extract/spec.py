"""매각물건명세서 원본(법원 문서뷰어 streamdocs 의 쪽별 글) → 임차인 줄(11/26 지시 1126a).

뷰어는 쪽마다 /streamdocs/v4/documents/<id>/texts/<쪽> 로 글 조각(text + 글자마다 rect)을 줌.
그림 PDF 가 아니라 글이라 자리(x · y)로 표를 다시 짬:
  점유자 성명 | 점유부분 | 정보출처 구분 | 점유의 권원 | 임대차기간 | 보증금 | 차임 | 전입신고일자 | 확정일자 | 배당요구여부(일자)
- 한 칸 글이 위아래로 여러 줄(이름 「한국주/택금융/공사」, 기간 「2020.04.02.~/2022.04.02」)이고 가운데 줄에 나머지 칸이 있음
  → 보증금 · 차임 · 배당요구 · 출처가 있는 줄을 「본 줄」로 잡고, 다른 줄은 가까운 본 줄에 붙임.
  이름 칸은 본 줄 사이 가장 넓은 틈에서 나눔(위아래 가운데 맞춤이라 가까운 본 줄로 붙이면 틀림).
- 같은 사람이 출처만 달리 두 줄(등기사항전부증명서 · 권리신고)이면 하나로 합침 — 보증금을 두 번 세지 않게.
"""

import re
from datetime import date
from typing import Any

from aucs_workers.extract.case_docs import parse_dot_date, parse_krw

Word = tuple[int, float, float, float, str]  # 쪽, 위(y — 클수록 위), 왼쪽, 오른쪽, 글

# 머리 칸 왼쪽(11/26 서울동부 · 중앙 · 남부 세 건 — 법원 양식이 같음). 머리를 찾으면 그 자리로 고침
COLS = [
    ("name", 0), ("part", 62), ("source", 108), ("title", 160), ("period", 192),
    ("deposit", 262), ("rent", 318), ("move_in", 378), ("fixed", 440), ("claim", 497),
]  # fmt: skip
MONEY = re.compile(r"^\d{1,3}(,\d{3})+$|^\d+$")
DATE = re.compile(r"\d{4}\.\d{1,2}\.\d{1,2}")
SOURCES = ("현황조사", "권리신고", "등기사항", "임차권", "부증명서", "전입세대", "주민등록")


def words_from_texts(pages: dict[int, list[dict[str, Any]]]) -> list[Word]:
    """쪽별 글 조각 → 낱말(빈칸 또는 6pt 넘는 틈에서 끊음). 글자 수와 rect 수가 다르면 조각을 비율로 나눔."""
    out: list[Word] = []
    for p in sorted(pages):
        for s in pages[p] or []:
            text, rects = str(s.get("text") or ""), s.get("rect") or []
            if not text.strip() or not rects:
                continue
            if len(rects) != len(text):
                x0, x1 = float(rects[0]["left"]), float(rects[-1]["right"])
                step = (x1 - x0) / max(1, len(text))
                rects = [
                    {"left": x0 + i * step, "right": x0 + (i + 1) * step, "top": rects[0]["top"]}
                    for i in range(len(text))
                ]
            cur, cx0, cx1, cy = "", 0.0, 0.0, 0.0
            for ch, r in zip(text, rects, strict=False):
                gap = cur and float(r["left"]) - cx1 > 6
                if ch.isspace() or gap:
                    if cur:
                        out.append((p, cy, cx0, cx1, cur))
                    cur = ""
                    if ch.isspace():
                        continue
                if not cur:
                    cx0, cy = float(r["left"]), float(r["top"])
                cur, cx1 = cur + ch, float(r["right"])
            if cur:
                out.append((p, cy, cx0, cx1, cur))
    return out


def _lines(ws: list[Word]) -> list[list[Word]]:
    """같은 쪽 · 같은 높이(2pt 안) 낱말 → 줄(위에서 아래로)."""
    ws = sorted(ws, key=lambda w: (w[0], -w[1], w[2]))
    out: list[list[Word]] = []
    for w in ws:
        if out and out[-1][0][0] == w[0] and abs(out[-1][0][1] - w[1]) <= 2:
            out[-1].append(w)
        else:
            out.append([w])
    return out


def _col(x: float, cols: list[tuple[str, float]]) -> str:
    name = cols[0][0]
    for n, left in cols:
        if x >= left:
            name = n
    return name


def _header_cols(lines: list[list[Word]]) -> list[tuple[str, float]]:
    """머리 줄(「보 증 금 차 임 … 확정일자 요구여부」)에서 칸 왼쪽을 고침 — 못 찾으면 기본값."""
    cols = dict(COLS)
    for ln in lines:
        t = {w[4]: w for w in ln}
        if "확정일자" in t and "요구여부" in t:
            cols["fixed"] = t["확정일자"][2] - 12
            cols["claim"] = t["요구여부"][2] - 22
            if "보" in t:
                cols["deposit"] = t["보"][2] - 10
            if "차" in t:
                cols["rent"] = t["차"][2] - 25
            break
    return sorted(cols.items(), key=lambda c: c[1])


def _is_main(ln: list[Word], cols: list[tuple[str, float]]) -> bool:
    for w in ln:
        c = _col((w[2] + min(w[3], w[2] + 40)) / 2, cols)
        if c in ("deposit", "rent") and MONEY.match(w[4]):
            return True
        if c == "claim":
            return True
        if c == "source" and any(w[4].startswith(s) for s in ("현황조사", "권리신고")):
            return True
    return False


def _join(parts: list[str]) -> str:
    out = ""
    for s in parts:
        if out and re.match(r"[가-힣(:)㈜]", s[:1]) and re.search(r"[가-힣(:)㈜]$", out):
            out += s
        else:
            out += (" " if out else "") + s
    return out


def _join_dates(parts: list[str]) -> str:
    """날짜 칸 조각 잇기 — 줄이 바뀌며 「2022.08.1 / 0.」처럼 나뉜 날짜를 붙임(11/27 성남 2025타경52870: 08-10 을 08-01 로 읽었음)."""
    out = ""
    for s in parts:
        if out and s[:1].isdigit() and (out[-1].isdigit() or out[-1] == "."):
            out += s
        else:
            out += (" " if out else "") + s
    return out


def table_words(ws: list[Word]) -> tuple[list[Word], bool]:
    """임차인 표 칸 안 낱말만(머리 아래 ~ 「<비고>」 위, 쪽을 넘으면 이어서). (낱말, 「조사된 임차내역없음」)"""
    out: list[Word] = []
    none = False
    on = False
    for ln in _lines(ws):
        text = " ".join(w[4] for w in ln)
        if "임차내역없음" in text.replace(" ", ""):
            none = True
        if re.search(r"신청일자$", text) and ln[0][2] > 300:  # 머리 끝 줄 「록 신청일자」
            on = True
            continue
        if on and (
            text.startswith("<비고>") or text.startswith("※") or text.startswith("등기된 부동산")
        ):
            on = False
            continue
        if on and re.fullmatch(r"\d+\s*/\s*\d+", text):  # 쪽 번호
            continue
        if on:
            out.extend(ln)
    return out, none


def parse_tenants(ws: list[Word]) -> dict[str, Any]:
    """낱말 → {"none": 임차내역 없음, "rows": [임차인 줄]}."""
    tws, none = table_words(ws)
    all_lines = _lines(ws)
    cols = _header_cols(all_lines)
    lines = _lines(tws)
    mains = [i for i, ln in enumerate(lines) if _is_main(ln, cols)]
    if not mains:
        return {"none": none, "rows": []}
    recs: list[dict[str, list[str]]] = [{} for _ in mains]

    def put(r: int, w: Word) -> None:
        c = _col(w[2] + 1, cols)
        recs[r].setdefault(c, []).append(w[4])

    # 본 줄 사이를 가장 넓은 틈에서 나눔 → 줄 i 가 몇 번째 본 줄 몫인지
    owner = [0] * len(lines)
    for k, m in enumerate(mains):
        lo = mains[k - 1] + 1 if k else 0
        if k:
            prev = mains[k - 1]
            gaps = [
                (
                    lines[j][0][1] - lines[j + 1][0][1]
                    if lines[j][0][0] == lines[j + 1][0][0]
                    else 99,
                    j,
                )
                for j in range(prev, m)
            ]
            cut = max(gaps)[1]  # cut 줄까지 앞 본 줄, 그다음부터 이 본 줄
            for j in range(lo, m + 1):
                owner[j] = k - 1 if j <= cut else k
        else:
            for j in range(0, m + 1):
                owner[j] = 0
    for j in range(mains[-1] + 1, len(lines)):
        owner[j] = len(mains) - 1
    for j, ln in enumerate(lines):
        for w in ln:
            c = _col(w[2] + 1, cols)
            if c == "name" or j in mains:
                put(owner[j], w)
            else:  # 다른 칸은 가까운 본 줄(위아래 한두 줄)
                near = min(
                    range(len(mains)),
                    key=lambda k: (
                        abs(lines[mains[k]][0][1] - w[1]) if lines[mains[k]][0][0] == w[0] else 999,
                        k,
                    ),
                )
                put(near, w)
    rows: list[dict[str, Any]] = []
    for r in recs:
        name = _join(r.get("name", []))
        dates_in = DATE.findall(_join_dates(r.get("move_in", [])))
        dates_fx = DATE.findall(_join_dates(r.get("fixed", [])))
        claim_t = _join_dates(r.get("claim", []))
        row = {
            "name": name or None,
            "part": " ".join(r.get("part", [])) or None,
            "source": _join(r.get("source", [])) or None,
            "title": _join(r.get("title", [])) or None,
            "period": "".join(r.get("period", [])) or None,
            "deposit_krw": parse_krw("".join(r.get("deposit", []))) if r.get("deposit") else None,
            "monthly_rent_krw": parse_krw("".join(r.get("rent", []))) if r.get("rent") else None,
            "move_in_date": parse_dot_date(dates_in[0]) if dates_in else None,
            "fixed_date": parse_dot_date(dates_fx[0]) if dates_fx else None,
            "claim_date": parse_dot_date(claim_t),
            "claim_text": claim_t or None,
        }
        if not row["name"] and rows:
            prev = rows[-1]
            # 한 사람 칸이 두 본 줄로 잡힌 경우(출처 줄 · 금액 줄이 따로) — 서로 비는 칸만 채우면 합침
            if (
                not row["source"]
                and not row["part"]
                and all(
                    prev.get(k) is None or row.get(k) is None or prev[k] == row[k]
                    for k in (
                        "deposit_krw",
                        "monthly_rent_krw",
                        "move_in_date",
                        "fixed_date",
                        "claim_date",
                    )
                )
            ):
                for k, v in row.items():
                    if v is not None and prev.get(k) is None:
                        prev[k] = v
                    elif k in ("title", "period") and v and prev.get(k) and v not in prev[k]:
                        prev[k] = prev[k] + v
                continue
            row["name"] = prev[
                "name"
            ]  # 이름 칸이 두 줄을 한 칸으로 묶은 경우(같은 사람 · 출처만 다름)
            row["name_shared"] = True
        rows.append(row)
    return {"none": none and not rows, "rows": merge_same(fix_names(rows))}


GUARANTORS = ("주택도시보증공사", "한국주택금융공사", "서울보증보험")


def fix_names(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """이름 칸이 줄을 넘어 앞뒤 사람에게 갈라 붙은 것을 바로잡음(11/27 — 진행 명세서 원본 524줄 중 109줄).

    ① 「유현성한국주택금융」 + 「공사(임차인:유현성)」 → 「유현성」 + 「한국주택금융공사(임차인:유현성)」
    ② 이름이 빈 줄은 보증금 · 전입일이 같은 다른 줄의 이름으로(같은 사람이 출처만 다른 줄 — 서울… 2025타경508836)."""
    rows = [dict(r) for r in rows]
    for i in range(len(rows) - 1):
        a, b = rows[i].get("name") or "", rows[i + 1].get("name") or ""
        for g in GUARANTORS:
            if b.startswith(g) or g in a:
                continue
            for k in range(len(g) - 1, 0, -1):
                if a.endswith(g[:k]) and b.startswith(g[k:]):
                    rows[i]["name"] = a[:-k] or None
                    rows[i + 1]["name"] = g + b[len(g) - k :]
                    break
            else:
                continue
            break
    for r in rows:
        if r.get("name") or not (r.get("deposit_krw") or r.get("move_in_date")):
            continue
        twin = next(
            (o for o in rows if o is not r and o.get("name")
             and o.get("deposit_krw") == r.get("deposit_krw") and o.get("move_in_date") == r.get("move_in_date")),
            None,
        )  # fmt: skip
        if twin:
            r["name"] = twin["name"]
    return rows


def merge_same(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """같은 사람 · 같은 보증금 · 같은 전입일 → 한 줄(출처는 합치고 배당요구 날짜는 있는 것)."""
    out: list[dict[str, Any]] = []
    for r in rows:
        # 「한국주택금융공사(임차인:김은)」처럼 임차인 권리를 이어받은 줄 → 그 임차인과 같은 보증금이면 한 줄(11/26 서울동부 2025타경51836)
        heir = re.search(r"\(임차인\s*:?\s*([^)]+)\)", r["name"] or "")
        who = heir.group(1).strip() if heir else r["name"]
        twin = next(
            (o for o in out if o["name"] == who
             and (o["deposit_krw"] == r["deposit_krw"]
                  # 11/27: 현황조사 줄(보증금 「미상」)과 권리신고 줄 — 같은 이름 · 같은 전입이면 한 사람
                  or (not heir and None in (o["deposit_krw"], r["deposit_krw"]) and o["move_in_date"] is not None))
             and (heir or o["move_in_date"] == r["move_in_date"])),
            None,
        )  # fmt: skip
        if not twin:
            out.append(dict(r))
            continue
        twin["source"] = " · ".join(x for x in (twin["source"], r["source"]) if x)
        if heir:
            twin["heir"] = r["name"]
        for k in ("claim_date", "fixed_date", "monthly_rent_krw", "part", "period", "deposit_krw"):
            if twin.get(k) is None and r.get(k) is not None:
                twin[k] = r[k]
        if twin.get("claim_date") is None and r.get("claim_text"):
            twin["claim_text"] = r["claim_text"]
    return out


def first_date(text: str | None) -> date | None:
    return parse_dot_date(text)
