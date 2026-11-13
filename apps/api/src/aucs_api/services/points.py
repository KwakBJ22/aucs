"""포인트 벌기(11/12 대표님, docs/design/11-points.md): 잔액 · 빈 물건 목록 · 맡기기 · 올린 서류 정산.

등기부는 기존 올리기 길(registry)을 그대로 쓰고, 읽기가 끝나면 settle_registry 가 공개 · 포인트를 정함.
감정평가서는 화면이 보관함(appraisal-uploads/<회원>/…)에 올린 것을 받아 사건번호를 맞춰 보고 원본 보관함에 넣음.
"""

import hashlib
from typing import Any

from aucs_rules.academy import ledger_key, table_key
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
_BALANCE_SQL = """select coalesce(sum(delta) filter (where delta > 0 and (expires_at is null or expires_at > now())), 0)
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
        "pay_max_pct": table.get("pay_max_pct"),
        "hold_minutes": table.get("hold_minutes"),
    }


_BOARD_WHERE = """
from core.items i join core.cases c using (case_id)
where i.display_policy = 'public' and i.sale_date between current_date and current_date + 30
  and i.status_code is distinct from 'gone' and coalesce(i.usage_name, '') !~ %(vehicles)s
  and (not exists (select 1 from app.uploaded_registries r where r.item_id = i.item_id and r.shared)
       or not exists (select 1 from core.appraisal_files f where f.case_id = i.case_id))
  and (%(item)s::text is null or i.item_id = %(item)s)
"""
_BOARD_SQL = (
    """
select i.item_id, i.case_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.building_desc, i.sigungu, i.gu,
       i.address,
       (select count(*) from app.watch_items w where w.item_id = i.item_id) as watchers,
       not exists (select 1 from app.uploaded_registries r where r.item_id = i.item_id and r.shared) as need_registry,
       not exists (select 1 from core.appraisal_files f where f.case_id = i.case_id) as need_appraisal,
       (select json_object_agg(h.kind, json_build_object('mine', h.user_id = %(uid)s, 'until', h.until_at, 'extended', h.extended))
          from app.contrib_holds h where h.item_id = i.item_id and h.until_at > now()) as holds
"""
    + _BOARD_WHERE
    + "order by i.sale_date, watchers desc, i.item_id offset %(offset)s limit %(limit)s"
)
PAGE = 30


def _row(r: dict[str, Any]) -> dict[str, Any] | None:
    """한 줄 → 화면 줄. 남이 맡긴 서류는 빼고, 둘 다 남이 맡겼으면 None."""
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
        return None
    return {
        "item_id": r["item_id"], "court": COURT_NAME.get(r["court_code"], r["court_code"]), "case_no": r["case_no"],
        "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
        "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x),
        "building": r["building_desc"] or r["usage_name"], "address": r["address"], "need": need,
    }  # fmt: skip


def board(uid: str, offset: int = 0, item: str | None = None) -> dict[str, Any]:
    """서류가 빈 물건(매각일 가깝고 관심 많은 순)을 30건씩 · 모두 몇 건인지. item 이 오면 그 물건을 맨 위에(상세에서 넘어옴)."""
    from aucs_rules.find_filter import VEHICLES

    base = {"uid": uid, "vehicles": VEHICLES}
    jobs = [
        (_BOARD_SQL, {**base, "item": None, "offset": offset, "limit": PAGE}),
        ("select count(*) as n " + _BOARD_WHERE, {**base, "item": None}),
    ]
    if item and offset == 0:
        jobs.append((_BOARD_SQL, {**base, "item": item, "offset": 0, "limit": 1}))
    with connect() as c:
        qs = batch(c, jobs)
        rows = qs[0].fetchall()
        total = qs[1].fetchone()
        first = qs[2].fetchall() if len(qs) > 2 else []
    out = [x for x in (_row(r) for r in first + [r for r in rows if r["item_id"] != item]) if x]
    return {"rows": out, "total": int(total["n"]) if total else 0, "next": offset + PAGE}


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
           on conflict (kind, sha256) do update set user_id = excluded.user_id, item_id = excluded.item_id,
               case_id = excluded.case_id, registry_upload_id = excluded.registry_upload_id,
               status = excluded.status, points = excluded.points, note = excluded.note,
               created_at = now(), decided_at = excluded.decided_at
             where app.contrib_uploads.status = 'rejected'  -- 안 맞다고 했던 파일은 다시 올려 볼 수 있게(11/14)
           returning contrib_id""",
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
            # 무료 기간(free_period)에 받은 것은 기한 없음 — 유료 전환일에 「그날부터 1년」으로 한꺼번에 정함(11/12)
            """insert into app.point_ledger (user_id, delta, reason, item_id, ref_id, expires_at)
               values (%s,%s,%s,%s,%s, case when %s then null else now() + make_interval(days => %s) end)""",
            (
                uid,
                pts,
                kind,
                item_id,
                r["contrib_id"],
                bool(t.get("free_period")),
                int(t.get("expire_days") or 365),
            ),
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


def my_appraisal(uid: str, item_id: str) -> dict[str, Any] | None:
    """이 물건에 내가 마지막으로 올린 감정평가서(상세 화면 한 줄, 11/14): 확인 대기 · 받은 포인트 · 반려."""
    with connect() as c:
        r = c.execute(
            """select status, points, note, created_at from app.contrib_uploads
               where user_id = %s and item_id = %s and kind = 'appraisal'
               order by contrib_id desc limit 1""",
            (uid, item_id),
        ).fetchone()
    if not r:
        return None
    return {"status": r["status"], "points": r["points"], "created_at": r["created_at"].isoformat(),
            "why": "review" if r["status"] == "review" else r["note"]}  # fmt: skip


def academy_done(uid: str) -> list[str]:
    """아카데미에서 포인트를 받은 단계들(「s0」)."""
    with connect() as c:
        rows = c.execute(
            "select item_id from app.point_ledger where user_id = %s and reason = 'academy'", (uid,)
        ).fetchall()
    return [str(r["item_id"]).split(":", 1)[-1] for r in rows]


def academy_grant(uid: str, stage: str) -> dict[str, Any]:
    """한 단계를 다 들었을 때 포인트(11/14) — 단계마다 한 번만(같은 줄이 있으면 그대로)."""
    key = ledger_key(stage)
    if not key:
        return {"points": 0, "why": "closed"}
    with connect() as c:
        t = _table(c)
        pts = int(t.get(table_key(stage)) or t.get("academy_stage") or 0)
        if not pts:
            return {"points": 0, "why": "closed"}
        r = c.execute(
            """insert into app.point_ledger (user_id, delta, reason, item_id, expires_at)
               values (%s, %s, 'academy', %s, case when %s then null else now() + make_interval(days => %s) end)
               on conflict (user_id, item_id) where reason = 'academy' do nothing returning entry_id""",
            (uid, pts, key, bool(t.get("free_period")), int(t.get("expire_days") or 365)),
        ).fetchone()
    return {"points": pts if r else 0, "why": "first" if r else "already"}


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
    """화면이 올린 감정평가서: 사건번호(또는 감정평가서 번호)가 맞으면 원본 보관함 + 요점 + 포인트.

    사건번호를 하나도 못 읽은 PDF(그림 PDF · 글은 있어도 표지가 그림인 PDF)는 PC 글자 인식 → 그래도 못 가르면 관리자.
    「아니다」고 바로 하는 것은 다른 사건번호가 또렷이 적혀 있을 때만(11/14 — 수원 2025타경59003: 사건번호가
    「타경(2025 59003)」으로 뽑혀 못 읽었는데 글이 있다고 바로 「안 맞음」, 같은 파일이라 다시 올릴 수도 없었음)."""
    from aucs_workers.extract.appraisal_pdf import case_numbers, has_report_no, read_pdf, same_case

    from aucs_api.services.registry import take_from_storage

    raw = take_from_storage(uid, path, APPRAISAL_IN)
    if raw is None:
        return {"ok": False, "why": "no_file"}
    with connect() as c:
        it = c.execute(
            """select i.case_id, c.case_no,
                      (select d.payload -> 'info' ->> 'aeeWevlNo' from raw.court_doc_raw d
                       where d.case_id = i.case_id and d.doc_kind = 'appraisal'
                       order by d.fetched_at desc limit 1) as report_no
               from core.items i join core.cases c using (case_id) where i.item_id = %s""",
            (item_id,),
        ).fetchone()
    if not it:
        return {"ok": False, "why": "no_item"}
    try:
        data = {"no": None, "from": "member", **read_pdf(raw)}
    except Exception:  # noqa: BLE001 — 깨진 PDF
        return {"ok": False, "why": "unreadable"}
    sha = hashlib.sha256(raw).hexdigest()
    head = str(data.get("head") or "")
    found = case_numbers(head)
    # 사건번호가 맞거나(사이에 글자가 껴도), 법원 감정평가 정보의 감정평가서 번호가 적혀 있으면 맞는 서류
    matched = same_case(head, it["case_no"]) or has_report_no(head, it["report_no"])
    scanned = not matched and not found  # 사건번호를 못 읽음 → 글자 인식으로
    if matched:
        _keep_appraisal(it["case_id"], data, raw)
    with connect() as c:
        got = _grant(c, uid, item_id, it["case_id"], "appraisal", sha, matched, review=scanned)
    if scanned and got.get("why") == "review":
        _storage("PUT", f"review/{sha}.pdf", raw)  # 관리자가 볼 때까지
    out = {"ok": matched or scanned, **got}
    if not matched and found and got.get("why") == "mismatch":
        out["found"] = found[:2]  # 파일에 적힌 사건번호를 알려 줌(왜 아니라는지)
    return out


def review_list() -> list[dict[str, Any]]:
    """관리자: 글 없는 그림 감정평가서(사건번호를 못 읽음) — 사람이 보고 맞으면 넣음."""
    with connect() as c:
        rows = c.execute(
            """select contrib_id, item_id, case_id, sha256, created_at, note from app.contrib_uploads
               where kind = 'appraisal' and status = 'review' order by contrib_id"""
        ).fetchall()
    from aucs_api import settings

    return [{**dict(r), "created_at": r["created_at"].isoformat(),
             "pdf": f"{settings.SUPABASE_URL}/storage/v1/object/authenticated/{APPRAISAL_IN}/review/{r['sha256']}.pdf"}
            for r in rows]  # fmt: skip


def ocr_waiting(limit: int = 5) -> list[dict[str, Any]]:
    """PC 글자 인식이 아직 안 본 그림 감정평가서(11/14) — note 가 'review' 그대로인 것."""
    with connect() as c:
        return [dict(r) for r in c.execute(
            """select u.contrib_id, c.case_no from app.contrib_uploads u
               join core.cases c on c.case_id = u.case_id
               where u.kind = 'appraisal' and u.status = 'review' and u.note = 'review'
               order by u.contrib_id limit %s""",
            (limit,),
        ).fetchall()]  # fmt: skip


def ocr_settle(contrib_id: int, matched: bool, why: str) -> bool:
    """글자 인식 결과: 사건번호가 맞으면 관리자가 맞다고 누른 것과 같이 넣고 포인트,
    아니면 까닭(ocr_none 못 읽음 · ocr_other 다른 사건번호)만 적고 관리자 확인에 둠."""
    if matched:
        return review_decide(contrib_id, True)
    with connect() as c:
        c.execute(
            "update app.contrib_uploads set note = %s where contrib_id = %s and status = 'review'",
            (why, contrib_id),
        )
    return False


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
