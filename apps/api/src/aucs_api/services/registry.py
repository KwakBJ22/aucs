"""회원이 올린 등기부: 받기 → (뒤에서) 읽기 → 권리 사다리·떠안는 돈.

읽기는 workers 의 등기부 추출(글자 PDF / 그림 PDF 글자 인식)을 그대로 씁니다.
판정은 요청할 때마다 규칙(aucs_rules.rights·tenants)으로 다시 해서, 규칙이 고쳐지면 바로 반영됩니다.
"""

import hashlib
import re
import tempfile
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from aucs_rules.address_match import compare
from aucs_rules.fix_dictionary import guess_purpose, names_for, normalize_purpose
from aucs_rules.fmt import won_small as won
from aucs_rules.payout import NamedTenant, payout
from aucs_rules.rights import Right, analyze
from aucs_rules.small_lease_region import region_class
from aucs_rules.tenants import (
    Tenant,
    claimed_in_time,
    flatten_small_lease_table,
    opposing_power,
)
from psycopg.types.json import Jsonb

from aucs_api.db import batch, connect
from aucs_api.services.docs import spec_sheet

MAX_BYTES = 10 * 1024 * 1024
KEEP_DAYS = 30  # 매각기일 뒤 원본 보관 날수 (10/18 대표님)
_CORP = re.compile(
    r"(주식회사|은행|공사|조합|공단|금고|캐피탈|보험|카드|신탁|저축|대부|국|시|군|구|청|세무서|㈜|\(주\))"
)


def mask_holder(name: str) -> str:
    """개인 이름(한글 2~4글자)만 가림: 홍길동 → 홍○○. 회사·기관은 그대로."""
    n = (name or "").strip()
    if re.fullmatch(r"[가-힣]{2,4}", n) and not _CORP.search(n):
        return n[0] + "○○"
    return n


def _iso(d: Any) -> str | None:
    return d.isoformat() if isinstance(d, date) else None


def right_to_json(r: Right) -> dict[str, Any]:
    d = asdict(r)
    d["receipt_date"] = _iso(r.receipt_date)
    d["move_in_date"] = _iso(r.move_in_date)
    d["holder"] = mask_holder(r.holder)
    d.pop("source", None)
    return d


def right_from_json(d: dict[str, Any]) -> Right:
    return Right(
        section=d["section"], rank_no=d["rank_no"], purpose=d["purpose"],
        receipt_date=date.fromisoformat(d["receipt_date"]) if d.get("receipt_date") else None,
        receipt_no=d.get("receipt_no"), amount_krw=d.get("amount_krw"),
        jeonse_claimed=bool(d.get("jeonse_claimed")), jeonse_whole_building=bool(d.get("jeonse_whole_building")),
        move_in_date=date.fromisoformat(d["move_in_date"]) if d.get("move_in_date") else None,
        holder=d.get("holder") or "",
    )  # fmt: skip


def apply_guesses(raw: list[dict[str, Any]]) -> tuple[list[Right], dict[tuple[str, str], str]]:
    """저장된 권리 → Right 목록 + 줄 표시(「추정」·「내가 고침」).

    손님이 고친 줄(fixed)은 그대로, 못 읽은 줄은 규칙으로 추정(guess_purpose)해서 판정에 씁니다."""
    rights, marks = [], {}
    for d in raw:
        r = right_from_json(d)
        key = (r.section, r.rank_no)
        if d.get("fixed"):
            marks[key] = "내가 고침"
        elif not normalize_purpose(r.purpose):
            g = guess_purpose(r.purpose, r.section, r.holder)
            if g:
                r = replace(r, purpose=g)
                marks[key] = "추정"
        rights.append(r)
    return rights, marks


def build_ladder(
    rights: list[Right],
    tenants: list[dict[str, Any]],
    claim_deadline: date | None,
    marks: dict[tuple[str, str], str] | None = None,
    price_krw: int | None = None,
    region_cls: str | None = None,
    small_table: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """권리 사다리(말소기준 선) + 대항력 임차인 + 떠안는 돈 (순수 함수, 결과는 추정)."""
    marks = marks or {}
    res = analyze(rights)
    base: Right | None = res["base"].value
    rows = []
    for r, j in res["rights"]:
        if j.value == "부기":
            continue
        rows.append({
            "section": r.section, "rank_no": r.rank_no, "name": normalize_purpose(r.purpose) or r.purpose,
            "date": _iso(r.receipt_date), "amount_krw": r.amount_krw, "holder": r.holder,
            "judgment": j.value, "is_base": r is base, "mark": marks.get((r.section, r.rank_no)),
        })  # fmt: skip
    assumed = [x for x in rows if x["judgment"] == "인수"]
    unknown_amount = any(x["amount_krw"] is None for x in assumed)
    hold = sum(x["amount_krw"] or 0 for x in assumed)
    t_rows = []
    partial = False
    tns = [
        Tenant(
            move_in_date=_d(t.get("move_in")),
            fixed_date=_d(t.get("fixed")),
            claim_date=_d(t.get("claim")),
            deposit_krw=t.get("deposit_krw"),
        )  # fmt: skip
        for t in tenants
    ]
    # 예상 배당: 보증금을 아는 임차인이 배당요구했을 때만 (최저가에 낙찰된다고 보고)
    pay = None
    if price_krw and any(
        tn.deposit_krw and claimed_in_time(tn, claim_deadline).value for tn in tns
    ):
        pay = payout(
            price_krw, rights,
            [NamedTenant(t.get("name") or "임차인", tn) for t, tn in zip(tenants, tns, strict=True)],
            base.receipt_date if base else None, claim_deadline, region_cls, small_table or [],
        )  # fmt: skip
    for idx, (t, tn) in enumerate(zip(tenants, tns, strict=True)):
        power = opposing_power(tn, base.receipt_date if base else None).value
        claimed = claimed_in_time(tn, claim_deadline).value
        got = pay["tenants"][idx] if pay else None
        if got and power is True and claimed and got["assume_krw"] is not None:
            a, rcv = got["assume_krw"], got["received_krw"]
            verdict = (
                f"배당에서 {won(rcv)} 받고 {won(a)}을 떠안아요"
                if a
                else "배당으로 보증금을 다 받아요"
            )
            add = a
        elif power is True and claimed is False:
            verdict, add = "보증금 전액을 떠안아요", tn.deposit_krw or 0
            unknown_amount = unknown_amount or tn.deposit_krw is None
        elif power is True:
            verdict, add, partial = "배당에서 못 받은 만큼 떠안을 수 있어요", 0, True
        elif power is False:
            verdict, add = "낙찰되면 대항력이 없어요", 0
            if got and got["received_krw"]:
                verdict += f" · 배당 {won(got['received_krw'])} 예상"
        else:
            verdict, add = "전입일을 몰라 판단할 수 없어요", 0
        hold += add
        t_rows.append({"name": t.get("name"), "move_in": t.get("move_in"), "deposit_krw": tn.deposit_krw,
                       "verdict": verdict, "power": power})  # fmt: skip
    if base is None:
        line, state = "말소기준이 되는 권리를 찾지 못했어요", "확인 필요"
    elif hold == 0 and not unknown_amount and not partial:
        unsure = sum(1 for x in rows if x["judgment"] == "확인 필요")
        guessed = sum(1 for x in rows if x["mark"] == "추정")
        line, state = (
            (f"떠안는 돈은 없어 보여요 · 읽기 어려운 줄 {unsure}개는 원문 확인", "확인 필요")
            if unsure
            else (f"떠안는 돈은 없어 보여요 · 추정한 줄 {guessed}개는 원문 확인", "추정")
            if guessed
            else ("떠안는 돈이 없어요", "추정")
        )
    elif hold == 0 and partial:
        line, state = "배당에서 못 받는 보증금만큼 떠안을 수 있어요", "확인 필요"
    elif unknown_amount:
        line, state = "떠안는 권리가 있는데 금액을 몰라요", "확인 필요"
    else:
        line, state = f"떠안는 돈 약 {won(hold)}" + (" + 배당 부족분" if partial else ""), "추정"
    return {
        "base": {"name": normalize_purpose(base.purpose) or base.purpose, "date": _iso(base.receipt_date)} if base else None,
        "rows": rows, "tenants": t_rows, "hold_krw": hold, "line": line, "state": state, "payout": pay,
    }  # fmt: skip


def _d(s: Any) -> date | None:
    if isinstance(s, date):
        return s
    try:
        return date.fromisoformat(str(s)) if s else None
    except ValueError:
        return None


# ── DB ──────────────────────────────────────────────


def save_upload(uid: str, item_id: str, file_name: str, data: bytes) -> int:
    """받은 PDF를 저장하고 upload_id 를 돌려줍니다(읽기는 parse_upload 가 뒤에서)."""
    with connect() as c:
        row = c.execute(
            "select sale_date from core.items where item_id = %s", (item_id,)
        ).fetchone()
        sale = row["sale_date"] if row and row["sale_date"] else date.today()
        r = c.execute(
            """insert into app.uploaded_registries (user_id, item_id, file_name, pdf, sha256, delete_after)
               values (%s,%s,%s,%s,%s,%s) returning upload_id""",
            (
                uid,
                item_id,
                file_name[:120],
                data,
                hashlib.sha256(data).hexdigest(),
                sale + timedelta(days=KEEP_DAYS),
            ),
        ).fetchone()
    assert r is not None
    return int(r["upload_id"])


def parse_upload(upload_id: int, ocr: bool = True) -> None:
    """PDF → 권리 목록. 그림 PDF는 글자 인식이라 수십 초 걸릴 수 있음.

    ocr=False(Vercel): 글자 있는 PDF 만 바로 읽고, 그림 PDF 는 method='ocr_wait' 로 두면
    PC 의 「관리자_요청」 작업(5분마다)이 글자 인식으로 마저 읽음(11/3 — Vercel 에는 tesseract 가 없음)."""
    from aucs_workers.extract.registry import read_pdf, read_pdf_text

    with connect() as c:
        r = c.execute(
            "select pdf from app.uploaded_registries where upload_id = %s", (upload_id,)
        ).fetchone()
    if r is None:
        return
    try:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "registry.pdf"
            p.write_bytes(bytes(r["pdf"]))
            got = read_pdf(p) if ocr else read_pdf_text(p)
            if got is None:
                with connect() as c:
                    c.execute(
                        "update app.uploaded_registries set method = 'ocr_wait' where upload_id = %s",
                        (upload_id,),
                    )
                return
            rights, meta = got
        if not rights:
            raise ValueError("등기부에서 권리를 찾지 못했어요")
        data = [right_to_json(x) for x in rights]
        with connect() as c:
            c.execute(
                """update app.uploaded_registries set status='parsed', method=%s, rights=%s, address=%s, parsed_at=now()
                   where upload_id=%s""",
                (meta.get("method"), Jsonb(data), meta.get("소재지"), upload_id),
            )
    except Exception as e:  # noqa: BLE001 — 어떤 오류든 손님에게는 「못 읽었어요」로
        with connect() as c:
            c.execute(
                "update app.uploaded_registries set status='failed', error=%s, parsed_at=now() where upload_id=%s",
                (str(e)[:300], upload_id),
            )


def latest(uid: str, item_id: str) -> dict[str, Any] | None:
    """이 물건에 내가 올린 마지막 등기부와 사다리."""
    case = "(select case_id from core.items where item_id = %(id)s)"
    with connect() as c:
        # 서로 상관없는 조회 5개를 한 번에 보냄(10/27 — 예전엔 차례로 5번 왕복)
        q_u, q_meta, q_spec, q_small, q_ten = batch(
            c,
            [
                (
                    """select upload_id, file_name, status, method, rights, error, delete_after, created_at, address, address_ok
                       from app.uploaded_registries where user_id = %(uid)s and item_id = %(id)s order by upload_id desc limit 1""",
                    {"uid": uid, "id": item_id},
                ),
                (
                    """select c.claim_deadline, i.case_id, i.item_no, i.min_price_krw, i.sido, i.sigungu, i.address
                       from core.items i join core.cases c using (case_id) where i.item_id = %(id)s""",
                    {"id": item_id},
                ),
                (
                    f"""select payload, fetched_at from raw.court_doc_raw where case_id = {case}
                       and doc_kind = 'item_detail_' || coalesce((select item_no from core.items
                       where item_id = %(id)s), 1) order by fetched_at desc limit 1""",
                    {"id": item_id},
                ),
                (
                    "select valid_from, valid_to, value from ref.rule_tables"
                    " where rule_key = 'small_lease_limit'",
                    None,
                ),
                (
                    f"""select name_masked as name, move_in_date::text as move_in, fixed_date::text as fixed,
                          claim_date::text as claim, deposit_krw from core.tenants where case_id = {case}""",
                    {"id": item_id},
                ),
            ],
        )
        u, meta, spec_row = q_u.fetchone(), q_meta.fetchone(), q_spec.fetchone()
        small_rows, tenants = q_small.fetchall(), q_ten.fetchall()
    if not u:
        return None
    spec = spec_sheet(spec_row["payload"]) if spec_row else None
    out = {
        "upload_id": u["upload_id"], "file_name": u["file_name"], "status": u["status"], "method": u["method"],
        "error": u["error"], "delete_after": u["delete_after"].isoformat(), "ladder": None,
        "created_at": u["created_at"].isoformat(), "choices": {"갑": names_for("갑"), "을": names_for("을")},
    }  # fmt: skip
    # 주소가 이 물건과 다르면(손님이 「그래도 보기」 누르기 전엔) 판정하지 않음
    if u["status"] == "parsed":
        m = compare(u["address"], meta["address"] if meta else None)
        out["address"] = {**m, "ok": u["address_ok"]}
        if m["result"] in ("different", "unit_differs") and not u["address_ok"]:
            return out
    if u["status"] == "parsed" and u["rights"]:
        rights, marks = apply_guesses(u["rights"])
        out["ladder"] = build_ladder(
            rights, tenants, meta["claim_deadline"] if meta else None, marks,
            price_krw=meta["min_price_krw"] if meta else None,
            region_cls=_region(meta, rights) if meta else None,
            small_table=flatten_small_lease_table([dict(r) for r in small_rows]),
        )  # fmt: skip
        out["ladder"]["spec_check"] = spec_base_check(
            out["ladder"]["base"], spec.get("base") if spec else None
        )
    return out


def spec_base_check(
    ladder_base: dict[str, Any] | None, spec_base: str | None
) -> dict[str, Any] | None:
    """등기부 말소기준 ↔ 명세서 최선순위 설정(「2021.3.31.근저당권」) 맞춰 보기. 둘 중 하나라도 없으면 None."""
    if not ladder_base or not ladder_base.get("date") or not spec_base:
        return None
    m = re.search(r"(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})", spec_base)
    if not m:
        return None
    sd = f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"
    return {"same": sd == ladder_base["date"], "spec": spec_base.strip(), "spec_date": sd,
            "registry_date": ladder_base["date"]}  # fmt: skip


def accept_address(uid: str, item_id: str) -> dict[str, Any] | None:
    """「그래도 이 등기부로 보기」."""
    with connect() as c:
        c.execute(
            """update app.uploaded_registries set address_ok = true where upload_id = (
                 select upload_id from app.uploaded_registries where user_id = %s and item_id = %s
                 order by upload_id desc limit 1)""",
            (uid, item_id),
        )
    return latest(uid, item_id)


def _region(meta: dict[str, Any], rights: list[Right]) -> str | None:
    """소액임차 지역 구분: 최초 담보물권 설정일 기준."""
    ds = [r.receipt_date for r in rights if r.section == "을" and r.receipt_date]
    base = min(ds) if ds else date.today()
    v = region_class(meta.get("sido"), meta.get("sigungu"), None, base).value
    return str(v) if v is not None else None


def fix_right(
    uid: str, item_id: str, section: str, rank_no: str, purpose: str
) -> dict[str, Any] | None:
    """손님이 고른 등기목적으로 그 줄을 고침(원래 읽은 글자는 read_as 로 남김)."""
    if purpose not in names_for(section):
        raise ValueError("고를 수 없는 이름이에요")
    with connect() as c:
        u = c.execute(
            """select upload_id, rights from app.uploaded_registries
               where user_id = %s and item_id = %s and status = 'parsed' order by upload_id desc limit 1""",
            (uid, item_id),
        ).fetchone()
        if not u:
            return None
        rights = list(u["rights"])
        hit = False
        for d in rights:
            if d["section"] == section and str(d["rank_no"]) == str(rank_no):
                d.setdefault("read_as", d["purpose"])
                d["purpose"], d["fixed"], hit = purpose, True, True
        if not hit:
            raise ValueError("그 줄을 찾지 못했어요")
        c.execute(
            "update app.uploaded_registries set rights = %s where upload_id = %s",
            (Jsonb(rights), u["upload_id"]),
        )
    return latest(uid, item_id)


def ocr_waiting(limit: int = 5) -> list[int]:
    """PC 에서 글자 인식으로 마저 읽을 등기부(Vercel 이 그림 PDF 라 남겨 둔 것 + 10분 넘게 읽는 중인 것)."""
    with connect() as c:
        rows = c.execute(
            """select upload_id from app.uploaded_registries
               where status = 'processing' and (method = 'ocr_wait' or created_at < now() - interval '10 minutes')
               order by upload_id limit %s""",
            (limit,),
        ).fetchall()
    return [int(r["upload_id"]) for r in rows]


BUCKET = "registry-uploads"


def take_from_storage(uid: str, path: str) -> bytes | None:
    """화면이 Supabase 파일 보관함에 바로 올린 PDF 를 받아 오고 보관함에서는 지움(11/3 — Vercel 은 4.5MB 까지만 받음)."""
    import httpx

    from aucs_api import settings

    if not path.startswith(f"{uid}/") or ".." in path or not settings.SUPABASE_SECRET_KEY:
        return None
    k = settings.SUPABASE_SECRET_KEY
    h = {"apikey": k, "Authorization": f"Bearer {k}"}
    url = f"{settings.SUPABASE_URL}/storage/v1/object"
    r = httpx.get(f"{url}/{BUCKET}/{path}", headers=h, timeout=30)
    if r.status_code != 200:
        return None
    httpx.request("DELETE", f"{url}/{BUCKET}", headers=h, json={"prefixes": [path]}, timeout=15)
    return r.content
