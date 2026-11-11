"""포인트 벌기(11/12 대표님, docs/design/11-points.md): 잔액 · 빈 물건 목록 · 맡기기 · 올린 서류 정산.

등기부는 기존 올리기 길(registry)을 그대로 쓰고, 읽기가 끝나면 settle_registry 가 공개 · 포인트를 정함.
감정평가서는 화면이 보관함(appraisal-uploads/<회원>/…)에 올린 것을 받아 사건번호를 맞춰 보고 원본 보관함에 넣음.
"""

import hashlib
from typing import Any

from aucs_rules.address_match import compare
from aucs_rules.points import points_for
from psycopg.types.json import Jsonb

from aucs_api.db import batch, connect
from aucs_api.services.items import COURT_NAME

_TABLE_SQL = (
    "select value from ref.rule_tables where rule_key = 'points' and valid_from <= current_date "
    "order by valid_from desc limit 1"
)
# 한국 날짜로 「오늘」 받은 건수(종류별)
_TODAY_SQL = """select kind, count(*) as n from app.contrib_uploads
                where user_id = %(uid)s and points > 0
                  and (created_at at time zone 'Asia/Seoul')::date = (now() at time zone 'Asia/Seoul')::date
                group by kind"""
_BALANCE_SQL = """select coalesce(sum(delta) filter (where delta > 0 and expires_at > now()), 0)
                       + coalesce(sum(delta) filter (where delta < 0), 0) as balance
                  from app.point_ledger where user_id = %(uid)s"""


def _table(c: Any) -> dict[str, Any]:
    r = c.execute(_TABLE_SQL).fetchone()
    return dict(r["value"]) if r else {}


def summary(uid: str) -> dict[str, Any]:
    """잔액 · 오늘 받은 건수 · 점수표."""
    with connect() as c:
        q_t, q_today, q_bal = batch(
            c, [(_TABLE_SQL, None), (_TODAY_SQL, {"uid": uid}), (_BALANCE_SQL, {"uid": uid})]
        )
        t = q_t.fetchone()
        table = dict(t["value"]) if t else {}
        today = {r["kind"]: int(r["n"]) for r in q_today.fetchall()}
        bal = q_bal.fetchone()
    return {
        "balance": max(0, int(bal["balance"])) if bal else 0,
        "today": {k: today.get(k, 0) for k in ("registry", "appraisal")},
        "max": table.get("daily_max") or {},
        "points": {k: table.get(k) for k in ("registry", "appraisal")},
        "hold_minutes": table.get("hold_minutes"),
    }


_BOARD_SQL = """
select i.item_id, i.case_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.building_desc, i.sigungu, i.gu,
       (select count(*) from app.watch_items w where w.item_id = i.item_id) as watchers,
       not exists (select 1 from app.uploaded_registries r where r.item_id = i.item_id and r.shared) as need_registry,
       not exists (select 1 from core.appraisal_files f where f.case_id = i.case_id) as need_appraisal,
       (select json_object_agg(h.kind, json_build_object('mine', h.user_id = %(uid)s, 'until', h.until_at, 'extended', h.extended))
          from app.contrib_holds h where h.item_id = i.item_id and h.until_at > now()) as holds
from core.items i join core.cases c using (case_id)
where i.display_policy = 'public' and i.sale_date between current_date and current_date + 30
  and i.status_code is distinct from 'gone'
  and (not exists (select 1 from app.uploaded_registries r where r.item_id = i.item_id and r.shared)
       or not exists (select 1 from core.appraisal_files f where f.case_id = i.case_id))
order by i.sale_date, watchers desc, i.item_id
limit %(limit)s
"""


def board(uid: str, limit: int = 60) -> list[dict[str, Any]]:
    """서류가 빈 물건(매각일 가깝고 관심 많은 순). 남이 맡긴 서류는 빼고, 둘 다 남이 맡겼으면 줄째 뺌."""
    with connect() as c:
        rows = c.execute(_BOARD_SQL, {"uid": uid, "limit": limit * 2}).fetchall()
    out = []
    for r in rows:
        holds = r["holds"] or {}
        need = {}
        for k in ("registry", "appraisal"):
            if not r[f"need_{k}"]:
                continue
            h = holds.get(k)
            if h and not h["mine"]:
                continue  # 다른 분이 맡아 떼는 중
            need[k] = {"until": h["until"] if h else None, "extended": bool(h and h["extended"])}
        if not need:
            continue
        out.append({
            "item_id": r["item_id"], "court": COURT_NAME.get(r["court_code"], r["court_code"]), "case_no": r["case_no"],
            "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
            "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x),
            "building": r["building_desc"] or r["usage_name"], "need": need,
        })  # fmt: skip
        if len(out) >= limit:
            break
    return out


def hold(uid: str, item_id: str, kind: str, extend: bool = False) -> dict[str, Any] | None:
    """맡기기(10분) · 「10분 더」(한 번). 남이 맡고 있으면 None."""
    with connect() as c:
        t = _table(c)
        mins = int(t.get("hold_extend_minutes" if extend else "hold_minutes") or 10)
        if extend:
            r = c.execute(
                """update app.contrib_holds set until_at = until_at + make_interval(mins => %s), extended = true
                   where item_id = %s and kind = %s and user_id = %s and until_at > now() and not extended
                   returning until_at, extended""",
                (mins, item_id, kind, uid),
            ).fetchone()
        else:
            r = c.execute(
                """insert into app.contrib_holds (item_id, kind, user_id, until_at)
                   values (%s, %s, %s, now() + make_interval(mins => %s))
                   on conflict (item_id, kind) do update set user_id = excluded.user_id,
                       until_at = excluded.until_at, extended = false
                   where app.contrib_holds.until_at <= now() or app.contrib_holds.user_id = excluded.user_id
                   returning until_at, extended""",
                (item_id, kind, uid, mins),
            ).fetchone()
    return {"until": r["until_at"].isoformat(), "extended": r["extended"]} if r else None


def _grant(c: Any, uid: str, item_id: str, case_id: str, kind: str, sha: str, matched: bool,
           registry_upload_id: int | None = None, review: bool = False) -> dict[str, Any]:  # fmt: skip
    """올린 서류 한 건을 적고 포인트를 정함(같은 파일은 한 번만)."""
    t = _table(c)
    q_today, q_prev = batch(c, [
        (_TODAY_SQL, {"uid": uid}),
        ("""select (now()::date - max(created_at)::date) as days from app.contrib_uploads
            where case_id = %s and kind = %s and points > 0""", (case_id, kind)),
    ])  # fmt: skip
    today = {r["kind"]: int(r["n"]) for r in q_today.fetchall()}.get(kind, 0)
    prev = q_prev.fetchone()
    days = prev["days"] if prev else None
    res = points_for(kind, t, matched=matched, today_count=today, paid_before=days is not None,
                     days_since_last_paid=days).value  # fmt: skip
    pts = 0 if review else int(res["points"])
    status = "review" if review else ("ok" if matched else "rejected")
    r = c.execute(
        """insert into app.contrib_uploads (user_id, item_id, case_id, kind, registry_upload_id, sha256, status, points, note, decided_at)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s, case when %s then null else now() end)
           on conflict (kind, sha256) do nothing returning contrib_id""",
        (
            uid,
            item_id,
            case_id,
            kind,
            registry_upload_id,
            sha,
            status,
            pts,
            "review" if review else res["why"],
            review,
        ),
    ).fetchone()
    if not r:
        return {"points": 0, "why": "same_file"}
    if pts:
        c.execute(
            """insert into app.point_ledger (user_id, delta, reason, item_id, ref_id, expires_at)
               values (%s,%s,%s,%s,%s, now() + make_interval(days => %s))""",
            (uid, pts, kind, item_id, r["contrib_id"], int(t.get("expire_days") or 365)),
        )
    c.execute("delete from app.contrib_holds where item_id = %s and kind = %s", (item_id, kind))
    return {"points": pts, "why": "review" if review else res["why"]}


def settle_registry(upload_id: int) -> None:
    """등기부 읽기가 끝난 뒤: 주소가 물건과 같으면 모든 회원에게 공개하고 포인트를 정함."""
    with connect() as c:
        u = c.execute(
            """select u.user_id, u.item_id, u.sha256, u.address, i.case_id, i.address as item_address
               from app.uploaded_registries u join core.items i using (item_id)
               where u.upload_id = %s and u.status = 'parsed'""",
            (upload_id,),
        ).fetchone()
        if not u:
            return
        same = compare(u["address"], u["item_address"])["result"] == "same"
        if same:
            c.execute(
                "update app.uploaded_registries set shared = true where upload_id = %s",
                (upload_id,),
            )
        _grant(
            c,
            str(u["user_id"]),
            u["item_id"],
            u["case_id"],
            "registry",
            u["sha256"],
            same,
            upload_id,
        )


def my_registry_points(uid: str, item_id: str) -> dict[str, Any] | None:
    """이 물건에 내가 마지막으로 올린 등기부의 포인트 결과(화면 한 줄)."""
    with connect() as c:
        r = c.execute(
            """select points, note from app.contrib_uploads where user_id = %s and item_id = %s and kind = 'registry'
               order by contrib_id desc limit 1""",
            (uid, item_id),
        ).fetchone()
    return {"points": r["points"], "why": r["note"]} if r else None


APPRAISAL_IN = "appraisal-uploads"


def _storage(method: str, path: str, content: bytes | None = None) -> Any:
    """감정평가서 받는 보관함을 서버 열쇠로(관리자 확인 기다리는 그림 PDF 를 잠깐 둠)."""
    import httpx

    from aucs_api import settings

    k = settings.SUPABASE_SECRET_KEY
    h = {"apikey": k, "Authorization": f"Bearer {k}"}
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{APPRAISAL_IN}"
    if method == "PUT":
        return httpx.post(f"{url}/{path}", headers={**h, "Content-Type": "application/pdf", "x-upsert": "true"},
                          content=content, timeout=60)  # fmt: skip
    if method == "GET":
        return httpx.get(f"{url}/{path}", headers=h, timeout=60)
    return httpx.request("DELETE", url, headers=h, json={"prefixes": [path]}, timeout=15)


def _keep_appraisal(case_id: str, data: dict[str, Any], raw: bytes) -> None:
    """맞는 감정평가서: 원본 보관함 + 요점(raw) — 수집기(appraisal_folder)와 같은 길."""
    from aucs_workers.collectors.appraisal_folder import upload
    from aucs_workers.collectors.parse import checksum
    from aucs_workers.db import connect as wconnect

    with wconnect() as wc:
        wc.execute(
            "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,'appraisal_pdf',%s,%s) on conflict do nothing",
            (case_id, Jsonb(data), checksum(data)),
        )
        wc.commit()
        upload(wc, case_id, data, raw)


def save_appraisal(uid: str, item_id: str, path: str) -> dict[str, Any]:
    """화면이 올린 감정평가서: 사건번호가 맞으면 원본 보관함 + 요점 + 포인트. 글 없는 그림 PDF 는 관리자 확인."""
    from aucs_workers.extract.appraisal_pdf import case_numbers, read_pdf

    from aucs_api.services.registry import take_from_storage

    raw = take_from_storage(uid, path, APPRAISAL_IN)
    if raw is None:
        return {"ok": False, "why": "no_file"}
    with connect() as c:
        it = c.execute(
            "select i.case_id, c.case_no from core.items i join core.cases c using (case_id) where i.item_id = %s",
            (item_id,),
        ).fetchone()
    if not it:
        return {"ok": False, "why": "no_item"}
    try:
        data = {"no": None, "from": "member", **read_pdf(raw)}
    except Exception:  # noqa: BLE001 — 깨진 PDF
        return {"ok": False, "why": "unreadable"}
    sha = hashlib.sha256(raw).hexdigest()
    found = case_numbers(str(data.get("head") or ""))
    scanned = not found and bool(data.get("scanned"))
    matched = it["case_no"] in found
    if matched:
        _keep_appraisal(it["case_id"], data, raw)
    with connect() as c:
        got = _grant(c, uid, item_id, it["case_id"], "appraisal", sha, matched, review=scanned)
    if scanned and got.get("why") == "review":
        _storage("PUT", f"review/{sha}.pdf", raw)  # 관리자가 볼 때까지
    return {"ok": matched or scanned, **got}


def review_list() -> list[dict[str, Any]]:
    """관리자: 글 없는 그림 감정평가서(사건번호를 못 읽음) — 사람이 보고 맞으면 넣음."""
    with connect() as c:
        rows = c.execute(
            """select contrib_id, item_id, case_id, sha256, created_at from app.contrib_uploads
               where kind = 'appraisal' and status = 'review' order by contrib_id"""
        ).fetchall()
    from aucs_api import settings

    return [{**dict(r), "created_at": r["created_at"].isoformat(),
             "pdf": f"{settings.SUPABASE_URL}/storage/v1/object/authenticated/{APPRAISAL_IN}/review/{r['sha256']}.pdf"}
            for r in rows]  # fmt: skip


def review_pdf(contrib_id: int) -> bytes | None:
    """관리자 확인용 원본(보관함이 잠겨 있어 서버가 대신 받아 줌)."""
    with connect() as c:
        r = c.execute(
            "select sha256 from app.contrib_uploads where contrib_id = %s", (contrib_id,)
        ).fetchone()
    if not r:
        return None
    g = _storage("GET", f"review/{r['sha256']}.pdf")
    return bytes(g.content) if g.status_code == 200 else None


def review_decide(contrib_id: int, ok: bool) -> bool:
    """맞으면 원본 보관함에 넣고 포인트, 아니면 반려. 확인 끝난 원본은 받는 보관함에서 지움."""
    from aucs_workers.extract.appraisal_pdf import read_pdf

    with connect() as c:
        r = c.execute(
            "select * from app.contrib_uploads where contrib_id = %s and status = 'review'",
            (contrib_id,),
        ).fetchone()
    if not r:
        return False
    path = f"review/{r['sha256']}.pdf"
    if ok:
        g = _storage("GET", path)
        if g.status_code != 200:
            return False
        raw = bytes(g.content)
        _keep_appraisal(r["case_id"], {"no": None, "from": "member", **read_pdf(raw)}, raw)
    with connect() as c:
        c.execute("delete from app.contrib_uploads where contrib_id = %s", (contrib_id,))
        _grant(c, str(r["user_id"]), r["item_id"], r["case_id"], "appraisal", r["sha256"], ok)
    _storage("DELETE", path)
    return True
