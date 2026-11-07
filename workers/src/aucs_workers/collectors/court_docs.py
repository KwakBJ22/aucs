"""사건 서류 데이터 수집: 사건내역·기일·문건송달·현황조사·물건상세 (화면과 같은 요청, 로그인 없음).

    uv run python -m aucs_workers.collectors.court_docs --archive        # 보관 수집 (서울·경기 아파트·다세대·오피스텔, 관심 물건 먼저)
    uv run python -m aucs_workers.collectors.court_docs --watched        # 관심에 담은 뒤 아직 서류를 안 받은 물건만(낮에 매시)
    uv run python -m aucs_workers.collectors.court_docs --next           # 유찰된 물건의 다음 회차·사진 미리(11/4, 하루 300)
    uv run python -m aucs_workers.collectors.court_docs --picks          # 홈에 뜰 물건 중 사진 없는 것(11/7, 가볍게)
    uv run python -m aucs_workers.collectors.court_docs --details        # 진행 물건 중 물건상세를 한 번도 안 받은 것(11/7, 가볍게)
    uv run python -m aucs_workers.collectors.court_docs --case B000250 2025타경55580

보관 규칙(10/16 결정): 매각기일 14일 안 1번 → 7일 안 1번 더 → 기일 뒤 1번, 하루 최대 150건(기일 가까운 순).
가볍게(11/7 — --picks·--next·--photos·--details): 물건상세만 받음. 사진·명세서 내용·감정 요점·기일 목록이 그 한 요청에 다 있음.
사건내역(물건 번호는 우리 목록에 있음)·기일내역(물건상세의 기일 목록으로 대신)은 건너뛰고, 감정평가서 정보는 사건당 한 번.
현황조사·문건송달은 입찰 2주 안에 서류 보관(--archive)이 받음. 사건 하나에 7번 → 1~2번.
명세서 PDF 는 받지 않습니다(데이터만). 감정평가서는 번호·가격시점만 받고 원본은 kapa_pdf(11/4). 원본은 raw 에 추가만 하므로
다시 받을 때 비어 온 종류는 예전 것이 그대로 남습니다.
"""

import argparse
import re
from datetime import date, timedelta
from typing import Any

import psycopg
from aucs_rules.find_filter import VEHICLES
from psycopg.types.json import Jsonb

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_site import COURTS
from aucs_workers.collectors.parse import checksum
from aucs_workers.collectors.polite import DailyLimitReached, Polite
from aucs_workers.db import connect
from aucs_workers.extract.case_docs import apply_case_docs, apply_next_sales, detail_schedule
from aucs_workers.jobs.runlog import run
from aucs_workers.photos import pull_pics
from aucs_workers.photos import store as store_photos

CASE_PAGE = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"
ARCHIVE_MAX = 150  # 11/4 오후: 300 → 150 (법원이 집 IP 를 막음), 대상은 모든 부동산 그대로
QUEUE_MAX = 10  # 5분마다: 손님이 연 물건의 서류(요청 줄) — 11/4 40 → 10
NEXT_MAX = 100  # 하루: 유찰된 물건의 다음 회차·사진 미리 받기(11/4, 300 → 100)
DETAILS_MAX = 300  # 한 번에: 물건상세 첫 바퀴(11/7 — 요항·토지건물 나눔·제시외·대지권을 모든 진행 물건에, 실제 양은 시간 몫이 정함)
DETAILS_DAYS = 45  # 입찰 이만큼 안의 진행 물건
PICKS_MAX = 300  # 한 번에: 홈에 뜰 물건 중 사진 없는 것(11/7 가볍게 받으므로 50 → 300, 실제 양은 시간 몫이 정함)
# 보관 대상 용도 (10/18: 아파트 → 다세대·연립·오피스텔까지, 하루 한도는 그대로)
ARCHIVE_USAGES = ("아파트", "다세대", "연립주택,다세대,빌라", "오피스텔")

JS_POST = r"""
async ([path, body]) => {
  const r = await fetch(path, { method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json' },
    body: JSON.stringify(body) });
  const t = await r.text();
  try { const j = JSON.parse(t); return { ok: r.ok && j.status == 200, status: r.status, msg: j.message, data: j.data }; }
  catch (e) { return { ok: false, status: r.status, msg: t.slice(0, 200) }; }
}
"""


def internal_no(case_no: str) -> str:
    """2023타경113350 → 20230130113350 (법원 내부 사건번호)."""
    m = re.fullmatch(r"(\d{4})타경(\d+)", case_no.replace(" ", ""))
    if not m:
        raise ValueError(f"사건번호 형식이 아닙니다: {case_no}")
    return f"{m.group(1)}0130{int(m.group(2)):06d}"


def archive_due(sale_date: date, last_fetched: date | None, today: date) -> tuple[bool, int]:
    """(받을 차례인지, 순서). 기일 14일 안 처음 → 7일 안 한 번 더 → 기일 뒤 한 번. 지난 것은 맨 뒤."""
    left = (sale_date - today).days
    if left > 14 or left < -7:
        return False, 0
    if left >= 0:
        need = last_fetched is None or (left <= 7 and last_fetched < sale_date - timedelta(days=7))
        return need, left
    return last_fetched is None or last_fetched <= sale_date, 100 - left


WATCHED_SQL = """
select c.court_code, c.case_no
from app.watch_items w
join core.items i using (item_id) join core.cases c using (case_id)
where i.sale_date between %(from)s and %(to)s and i.status_code is distinct from 'gone'
group by c.case_id, c.court_code, c.case_no
having coalesce((select max(fetched_at) from raw.court_doc_raw r where r.case_id = c.case_id), '-infinity')
       < max(w.created_at)
order by min(i.sale_date)
"""


def watched_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """관심에 담은 뒤 아직 서류를 안 받은 사건(용도 상관없이, 기일 60일 안). 「관심 담으면 바로 준비」(16)."""
    rows = conn.execute(
        WATCHED_SQL, {"from": today - timedelta(days=7), "to": today + timedelta(days=60)}
    ).fetchall()
    return [(court, case_no) for court, case_no in rows if court in COURTS]


PHOTO_SQL = """
select c.court_code, c.case_no, min(i.sale_date) as d,
       bool_or(exists (select 1 from app.watch_items w where w.item_id = i.item_id)) as watched
from core.cases c join core.items i using (case_id)
where i.sale_date >= %s
  and exists (select 1 from raw.court_doc_raw r where r.case_id = c.case_id and r.doc_kind like 'item_detail_%%')
  and not exists (select 1 from core.item_photos p where p.case_id = c.case_id)
group by 1, 2 order by watched desc, d
limit %s
"""


def photo_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """사진 다시 받기(11/1 사진을 원문에서 빼면서 키가 비어 못 옮긴 것): 관심 먼저, 기일 가까운 순."""
    rows = conn.execute(PHOTO_SQL, (today, ARCHIVE_MAX * 4)).fetchall()
    return [(court, case_no) for court, case_no, _, _ in rows if court in COURTS]


REAL_ESTATE = f"coalesce(i.usage_name, '') !~ '{VEHICLES}'"  # 부동산만 — 규칙 FIND-03 한 곳
AREA = "i.sido in ('서울특별시', '경기도', '인천광역시')"
LIVE_FIRST = "case when i.usage_name = any(%(usages)s) then 0 else 1 end"


def next_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """유찰된 뒤 아직 다음 기일을 모르는 사건(지난 2주) — 아파트류 먼저, 감정가 대비 싼 순(11/4).

    물건상세의 기일 목록으로 apply_next_sales 가 다음 기일·최저가를 넣음(11/7). 사진도 같이 받음.
    """
    rows = conn.execute(
        f"""select c.court_code, c.case_no
            from core.items i join core.cases c using (case_id)
            where {AREA} and {REAL_ESTATE} and i.sale_date < %(today)s and i.sale_date >= %(since)s
              and exists (select 1 from core.sale_results s where s.item_id = i.item_id and s.result = 'failed'
                          and s.sale_date = i.sale_date)
              and not exists (select 1 from raw.court_doc_raw r where r.case_id = c.case_id
                              and (r.doc_kind = 'schedule' or r.doc_kind like 'item_detail_%%')
                              and r.fetched_at::date > i.sale_date)
            group by c.case_id, c.court_code, c.case_no
            order by min({LIVE_FIRST}), min(i.min_price_krw::float / nullif(i.appraisal_krw, 0))
            limit %(n)s""",
        {"today": today, "since": today - timedelta(days=14), "usages": list(ARCHIVE_USAGES), "n": NEXT_MAX},
    ).fetchall()  # fmt: skip
    return [(court, case_no) for court, case_no in rows if court in COURTS]


def pick_photo_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """홈에 뜰 물건(11/7) 가운데 사진이 없는 사건 — 입찰 14일 안 공고된 것 + 유찰 뒤 다음 회차(35일 안).

    홈은 사진 있는 물건만 띄우므로 이것이 먼저. 아파트류 먼저, 감정가 대비 싼 순.
    """
    rows = conn.execute(
        f"""select c.court_code, c.case_no
            from core.items i join core.cases c using (case_id)
            where {AREA} and {REAL_ESTATE} and i.status_code is distinct from 'gone'
              and (i.sale_date between %(today)s and %(to)s
                   or (i.status_code = 'preview' and i.sale_date between %(today)s and %(to_next)s))
              and not exists (select 1 from core.item_photos p where p.case_id = c.case_id)
              -- 매시 돌므로(11/4) 법원에 사진이 없는 사건을 매번 다시 받지 않게 사흘에 한 번만
              and not exists (select 1 from raw.court_doc_raw r where r.case_id = c.case_id
                              and r.fetched_at > now() - interval '3 days')
            group by c.case_id, c.court_code, c.case_no
            order by min({LIVE_FIRST}), min(i.min_price_krw::float / nullif(i.appraisal_krw, 0))
            limit %(n)s""",
        {"today": today, "to": today + timedelta(days=14), "to_next": today + timedelta(days=35),
         "usages": list(ARCHIVE_USAGES), "n": PICKS_MAX},
    ).fetchall()  # fmt: skip
    return [(court, case_no) for court, case_no in rows if court in COURTS]


def details_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """진행 물건(입찰 45일 안) 가운데 물건상세를 한 번도 안 받은 사건 — 입찰 가까운 순, 아파트류 먼저(11/7).

    요항·사진·명세서 내용·토지건물 감정가·제시외 건물·대지권이 물건상세 한 번에 있어 모든 진행 물건에 한 번씩 받음.
    물건 번호가 많은 사건(6개 넘음)은 요청이 많아 뒤로."""
    rows = conn.execute(
        f"""select c.court_code, c.case_no
            from core.items i join core.cases c using (case_id)
            where {AREA} and {REAL_ESTATE} and i.status_code is distinct from 'gone'
              and i.sale_date between %(today)s and %(to)s
              and not exists (select 1 from raw.court_doc_raw r where r.case_id = c.case_id
                              and (r.doc_kind like 'item_detail_%%' or r.fetched_at > now() - interval '3 days'))
            group by c.case_id, c.court_code, c.case_no
            order by (count(distinct i.item_no) > 6), min(i.sale_date), min({LIVE_FIRST})
            limit %(n)s""",
        {"today": today, "to": today + timedelta(days=DETAILS_DAYS), "usages": list(ARCHIVE_USAGES),
         "n": DETAILS_MAX},
    ).fetchall()  # fmt: skip
    return [(court, case_no) for court, case_no in rows if court in COURTS]


def queue_targets(conn: psycopg.Connection) -> tuple[list[tuple[str, str]], list[int]]:
    """손님이 연 물건의 서류 요청(ops.job_requests 'case_docs:<item_id>')을 오래된 것부터 — 받을 사건과 요청 번호(11/4)."""
    rows = conn.execute(
        """update ops.job_requests r set status = 'running', started_at = now()
           where r.req_id in (select req_id from ops.job_requests where status = 'waiting' and job_key like 'case_docs:%%'
                              order by requested_at limit %s for update skip locked)
           returning r.req_id, substr(r.job_key, 11) as item_id""",
        (QUEUE_MAX,),
    ).fetchall()
    conn.commit()
    ids = [req for req, _ in rows]
    if not ids:
        return [], []
    cases = conn.execute(
        """select distinct c.court_code, c.case_no from core.items i join core.cases c using (case_id)
           where i.item_id = any(%s)""",
        ([item for _, item in rows],),
    ).fetchall()
    return [(court, no) for court, no in cases if court in COURTS], ids


def archive_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    rows = conn.execute(
        f"""select c.court_code, c.case_no, min(i.sale_date),
                  (select max(fetched_at)::date from raw.court_doc_raw r where r.case_id = c.case_id)
           from core.items i join core.cases c using (case_id)
           where {REAL_ESTATE} and {AREA}
             and i.sale_date between %s and %s
           group by c.case_id, c.court_code, c.case_no""",
        (today - timedelta(days=7), today + timedelta(days=14)),
    ).fetchall()
    todo = []
    for court, case_no, sale_date, last in rows:
        need, rank = archive_due(sale_date, last, today)
        if need and court in COURTS:
            todo.append((rank, court, case_no))
    todo.sort()
    first = watched_targets(conn, today)  # 관심 물건 먼저
    rest = [(c, n) for _, c, n in todo if (c, n) not in set(first)]
    return (first + rest)[:ARCHIVE_MAX]


def fetch_case(
    page: Any, polite: Polite, court: str, case_no: str,
    light_seqs: list[int] | None = None, need_appraisal: bool = True,
) -> dict[str, dict[str, Any]]:  # fmt: skip
    """한 사건의 서류 데이터를 종류별로 받습니다. 물건상세가 실패하면 그 종류만 빠집니다.

    light_seqs 가 있으면(11/7 가볍게) 그 물건 번호의 물건상세만 — 사건내역·기일·문건송달·현황조사는 건너뜀."""
    cs = internal_no(case_no)

    def post(path: str, body: dict[str, Any], label: str) -> dict[str, Any]:
        res = polite.call(lambda: dict(page.evaluate(JS_POST, [path, body])), f"{case_no} {label}")
        return dict(res.get("data") or {})

    out: dict[str, dict[str, Any]] = {}
    if light_seqs:
        _details(post, court, cs, light_seqs, out)
        if need_appraisal:
            out["appraisal"] = fetch_appraisal_info(post, court, cs, out)
        return out
    out["case_info"] = post(
        "/pgj/pgj15A/selectAuctnCsSrchRslt.on",
        {"dma_srchCsDtlInf": {"cortOfcCd": court, "csNo": case_no}},
        "사건내역",
    )
    out["schedule"] = post(
        "/pgj/pgj15A/selectCsDtlDxdyDts.on",
        {"dma_srchDxdyDtsLst": {"cortOfcCd": court, "csNo": cs}},
        "기일내역",
    )
    out["deliveries"] = post(
        "/pgj/pgj15A/selectDlvrOfdocDtsDtl.on",
        {"dma_srchDlvrOfdocDts": {"cortOfcCd": court, "csNo": cs, "srchFlag": "F"}},
        "문건송달",
    )
    out["status_report"] = post(
        "/pgj/pgj15B/selectCurstExmndc.on",
        {
            "dma_srchCurstExmn": {
                "cortOfcCd": court,
                "csNo": case_no,
                "auctnInfOriginDvsCd": "2",
                "ordTsCnt": "",
            }
        },
        "현황조사",
    )
    seqs = sorted(
        {
            int(g.get("dspslGdsSeq") or 1)
            for g in out["case_info"].get("dlt_dspslGdsDspslObjctLst") or []
        }
        or {1}
    )
    _details(post, court, cs, seqs, out)
    out["appraisal"] = fetch_appraisal_info(post, court, cs, out)
    return out


def _details(
    post: Any, court: str, cs: str, seqs: list[int], out: dict[str, dict[str, Any]]
) -> None:
    """물건상세(물건 번호마다 한 번) — 사진·명세서 내용·감정 요점·기일 목록이 다 들어 있음."""
    for seq in seqs:
        body = {
            "dma_srchGdsDtlSrch": {
                "csNo": cs,
                "cortOfcCd": court,
                "dspslGdsSeq": seq,
                "pgmId": "PGJ15BM01",
                "srchInfo": {},
            }
        }
        try:
            out[f"item_detail_{seq}"] = post(
                "/pgj/pgj15B/selectAuctnCsSrchRslt.on", body, f"물건상세{seq}"
            )
        except DailyLimitReached:
            raise  # 한도 — 이 사건은 저장하지 않고 다음 시간에 처음부터(반쪽 저장 막기)
        except Exception as e:  # noqa: BLE001 — 물건상세만 실패하면 나머지는 저장
            if type(e).__name__ == "Blocked" and "물건상세" not in str(e):
                raise


def fetch_appraisal_info(
    post: Any, court: str, cs: str, out: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """감정평가서 정보(11/4 — KAPA 허락): 감정서 번호 · 가격시점 · 작성일. 화면 「감정평가서 보기」 팝업(PGJ15BP03)과 같은 요청.

    원본 PDF 는 이 번호로 kapa_pdf 수집기가 받음. 감정평가서가 없는 사건은 빈 값. 실패해도 다른 서류는 저장."""
    info = next((d.get("dma_result", {}).get("dspslGdsDxdyInfo") or {} for k, d in out.items()
                 if k.startswith("item_detail_") and d), {})  # fmt: skip
    body = {"dma_srchAeeWevl": {"cortOfcCd": court, "cortSptNm": COURTS.get(court, ""), "csNo": cs,
                                "auctnInfOriginDvsCd": "4", "dspslDxdyYmd": info.get("dspslDxdyYmd") or "",
                                "pgmId": "PGJ15BP03"}}  # fmt: skip
    try:
        d = post("/pgj/pgj15B/selectAeeWevlInfo.on", body, "감정평가서 정보")
    except DailyLimitReached:
        raise
    except Exception:  # noqa: BLE001
        return {}
    inf = d.get("dma_ordTsIndvdAeeWevlInf") or {}
    if not inf.get("aeeWevlNo"):
        return {}
    # ipcheck 같은 접속 정보는 버리고 감정서 칸만
    return {"info": inf, "orders": d.get("dlt_aeeWevlOrdTsLst") or []}


def save_case(
    conn: psycopg.Connection, court: str, case_no: str, docs: dict[str, dict[str, Any]]
) -> None:
    case_id = f"{court}-{case_no}"
    conn.execute(
        "insert into core.cases (case_id, court_code, case_no) values (%s,%s,%s) on conflict do nothing",
        (case_id, court, case_no),
    )
    pics: list[tuple[str, str]] = []
    for kind in list(docs):
        if kind.startswith("item_detail_") and docs[kind]:
            docs[kind], got = pull_pics(
                docs[kind]
            )  # 사진 글자는 원문에서 빼고 줄여서 Storage 로(11/1)
            pics += got
    for kind, data in docs.items():
        if not data:
            continue  # 비어 온 종류는 넣지 않음 → 예전 것 유지
        conn.execute(
            "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,%s,%s,%s) on conflict do nothing",
            (case_id, kind, Jsonb(data), checksum(data)),
        )
    apply_case_docs(conn, case_id, docs)
    if "schedule" not in docs:  # 가볍게 받았으면 물건상세의 기일 목록으로 다음 회차(11/7)
        for kind, data in docs.items():
            if kind.startswith("item_detail_") and data:
                apply_next_sales(conn, case_id, detail_schedule(data, int(kind.rsplit("_", 1)[1])))
    store_photos(conn, case_id, pics)


def _known(conn: psycopg.Connection, court: str, case_no: str) -> tuple[list[int], bool]:
    """우리 목록에 있는 물건 번호들과 감정평가서 정보를 이미 받았는지 — 가볍게 받을 때 법원에 다시 묻지 않으려고."""
    case_id = f"{court}-{case_no}"
    seqs = [r[0] for r in conn.execute(
        "select distinct item_no from core.items where case_id = %s and item_no is not null order by 1", (case_id,)
    ).fetchall()]  # fmt: skip
    apr = conn.execute(
        "select 1 from raw.court_doc_raw where case_id = %s and doc_kind = 'appraisal' limit 1",
        (case_id,),
    ).fetchone()
    return seqs, apr is not None


def main() -> None:

    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", action="store_true")
    ap.add_argument("--watched", action="store_true", help="관심에 담은 뒤 아직 안 받은 서류만")
    ap.add_argument(
        "--photos", action="store_true", help="진행 중인데 현장 사진이 없는 사건만 다시 받기(11/1)"
    )
    ap.add_argument(
        "--next", action="store_true", help="유찰된 물건의 다음 회차·사진 미리 받기(11/4)"
    )
    ap.add_argument("--picks", action="store_true", help="추천 후보 중 사진 없는 것(11/4)")
    ap.add_argument("--details", action="store_true", help="물건상세를 안 받은 진행 물건(11/7)")
    ap.add_argument(
        "--queue", action="store_true", help="손님이 연 물건의 서류 요청(11/4, 5분마다)"
    )
    ap.add_argument("--case", nargs=2, metavar=("법원코드", "사건번호"))
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    # 손님이 연 물건(--queue)·한 사건(--case)은 시간 몫과 상관없이(하루 전체 한도에는 셈)
    polite = Polite(
        daily_limit=NEXT_MAX * 8 if a.next else ARCHIVE_MAX * 12, hourly=not (a.queue or a.case)
    )
    req_ids: list[int] = []
    try:
        _run(a, polite, req_ids)
    finally:
        if req_ids:  # 손님 요청 줄은 받았든 못 받았든 끝냄(다음 날 다시 줄 설 수 있음)
            with connect() as conn:
                conn.execute(
                    "update ops.job_requests set status = 'done', finished_at = now(), message = '서류 받음' where req_id = any(%s)",
                    (req_ids,),
                )
                conn.commit()


def _run(a: argparse.Namespace, polite: Polite, req_ids: list[int]) -> None:
    from playwright.sync_api import sync_playwright

    with connect() as conn, run(conn, "court_docs", "사건 서류 보관") as job:
        if a.case:
            targets = [tuple(a.case)]
        elif a.watched:
            targets = watched_targets(conn, date.today())
        elif a.photos:
            targets = photo_targets(conn, date.today())
        elif a.next:
            targets = next_targets(conn, date.today())
        elif a.queue:
            targets, ids = queue_targets(conn)
            req_ids.extend(ids)
        elif a.picks:
            targets = pick_photo_targets(conn, date.today())
        elif a.details:
            targets = details_targets(conn, date.today())
        else:
            targets = archive_targets(conn, date.today())
        print(f"대상 {len(targets)}건")
        if not targets:
            return
        light = bool(a.picks or a.next or a.photos or a.details)
        with sync_playwright() as p:
            browser = launch_chrome(p, headless=not a.show)
            page = browser.new_page()
            page.goto(CASE_PAGE, wait_until="networkidle", timeout=60000)
            try:
                for court, case_no in targets:
                    try:
                        seqs, has_apr = _known(conn, court, case_no) if light else ([], False)
                        # 첫 바퀴(--details)는 물건상세만 — 감정평가서 정보(가격시점)는 홈 사진·서류 보관 때 받음
                        docs = fetch_case(
                            page, polite, court, case_no, seqs or None, not (has_apr or a.details)
                        )
                    except DailyLimitReached:
                        print("요청 한도(이번 시간 몫 또는 하루) — 다음 시간에 이어서")
                        break
                    save_case(conn, court, case_no, docs)
                    conn.commit()
                    job.count += 1
                    polite.between_cases()
            finally:
                browser.close()
    print(f"끝: {job.count}건")


if __name__ == "__main__":
    main()
