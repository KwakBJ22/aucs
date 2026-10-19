"""알림 만들기·보내기 (하루 한 번, 분석 뒤).

1) 저장한 조건: 조건을 저장한 뒤 처음 들어온 물건만 '새 물건'으로 모아 한 통.
2) 관심 물건: 매각기일·최저가·결과가 바뀌면 한 통씩. 처음 본 값은 기준으로만 적고 알리지 않음.
3) 입찰 전 확인(실패 예방 3단계): 기일 7일 전 「명세서가 나왔어요」, 입찰일 아침(--morning) 「오늘 다시 볼 것」.
4) 낙찰 받은 물건: 대금기한·취득세·인도명령 마감 3일 전에 한 통씩(일정은 aucs_rules.schedule).
같은 (사람, 물건, 종류, 새 값)은 app.alert_events 의 unique 로 한 번만.
"""

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from aucs_rules.schedule import after_sale, short

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

WATCH_KINDS = ("sale_date", "min_price", "result", "listing")
RESULT_KO = {
    "sold": "매각",
    "failed": "유찰",
    "changed": "변경",
    "withdrawn": "취하",
    "dismissed": "기각",
}


@dataclass(frozen=True)
class Change:
    kind: str
    prev: str | None
    new: str


def watch_changes(prev: dict[str, str], cur: dict[str, str | None]) -> list[Change]:
    """지난 값과 지금 값을 비교. 지난 값이 없으면 기준(prev=None)으로만 돌려줌."""
    out = []
    for k in WATCH_KINDS:
        v = cur.get(k)
        if v is None or prev.get(k) == v:
            continue
        out.append(Change(k, prev.get(k), v))
    return out


def change_text(place: str, ch: Change) -> tuple[str, str]:
    if ch.kind == "sale_date":
        return f"{place} 매각기일이 바뀌었어요", f"{ch.prev} → {ch.new}"
    if ch.kind == "min_price":
        a, b = int(ch.prev or 0), int(ch.new)
        return f"{place} 최저가가 {'내렸' if b < a else '올랐'}어요", f"{won(a)} → {won(b)}"
    if ch.kind == "listing":
        if ch.new == "gone":
            return (
                f"{place} 법원 목록에서 빠졌어요",
                "기일 변경이나 취하일 수 있어요 · 법원에서 확인하세요",
            )
        return f"{place} 다시 법원 목록에 올라왔어요", "매각기일과 최저가를 확인해 보세요"
    return f"{place} {RESULT_KO.get(ch.new, ch.new)}", "결과를 확인해 보세요"


def won(v: int) -> str:
    eok, man = divmod(v // 10_000, 10_000)
    if eok and man:
        return f"{eok}억 {man:,}만원"
    return f"{eok}억원" if eok else f"{man:,}만원"


def match_sql(filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """찾기 화면과 같은 기준(시군구, 최저가/10 ≤ 현금)."""
    sql = "i.sale_date >= current_date and i.status_code is distinct from 'gone'"
    p: dict[str, Any] = {}
    if filters.get("sigungu"):
        sql += " and i.sigungu = any(%(sigungu)s)"
        p["sigungu"] = list(filters["sigungu"])
    if filters.get("max_cash"):
        sql += " and i.min_price_krw / 10 <= %(max_cash)s"
        p["max_cash"] = int(filters["max_cash"])
    return sql, p


def _event(
    conn: psycopg.Connection, uid: Any, item_id: str, kind: str, prev: str | None, new: str
) -> int | None:
    row = conn.execute(
        "insert into app.alert_events (user_id, item_id, kind, prev_value, new_value) values (%s,%s,%s,%s,%s) "
        "on conflict do nothing returning event_id",
        (uid, item_id, kind, prev, new),
    ).fetchone()
    return int(row[0]) if row else None


def _noti(
    conn: psycopg.Connection, uid: Any, event_id: int | None, title: str, body: str, link: str
) -> None:
    conn.execute(
        "insert into app.notifications (user_id, event_id, title, body, link) values (%s,%s,%s,%s,%s)",
        (uid, event_id, title, body, link),
    )


def make_search_alerts(conn: psycopg.Connection) -> int:
    n = 0
    for sid, uid, name, filters, since in conn.execute(
        "select search_id, user_id, name, filters, created_at from app.saved_searches where active"
    ).fetchall():
        cond, p = match_sql(filters)
        rows = conn.execute(
            f"""select i.item_id from core.items i
                where {cond} and (select min(fetched_at) from raw.court_item_raw r where r.doc_key = i.doc_key) > %(since)s""",
            {**p, "since": since},
        ).fetchall()
        fresh = [r[0] for r in rows if _event(conn, uid, r[0], "new_match", None, str(sid))]
        if fresh:
            _noti(
                conn,
                uid,
                None,
                f"{name}에 새 물건 {len(fresh)}건",
                "오늘 새로 올라온 물건이에요",
                "/home",
            )
            n += 1
    return n


def make_watch_alerts(conn: psycopg.Connection) -> int:
    n = 0
    rows = conn.execute(
        """select w.user_id, i.item_id, coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, ''),
                  i.sale_date::text, i.min_price_krw::text,
                  (select result from core.rounds r where r.item_id = i.item_id and r.result <> 'scheduled'
                   order by sale_date desc limit 1),
                  case when i.status_code = 'gone' then 'gone' else 'listed' end
           from app.watch_items w join core.items i using (item_id)"""
    ).fetchall()
    for uid, item_id, place, sale_date, min_price, result, listing in rows:
        prev: dict[str, str] = dict(
            conn.execute(
                """select distinct on (kind) kind, new_value from app.alert_events
                   where user_id = %s and item_id = %s and kind = any(%s) order by kind, created_at desc""",
                (uid, item_id, list(WATCH_KINDS)),
            ).fetchall()
        )
        cur = {
            "sale_date": sale_date,
            "min_price": min_price,
            "result": result,
            "listing": listing,
        }
        for ch in watch_changes(prev, cur):
            eid = _event(conn, uid, item_id, ch.kind, ch.prev, ch.new)
            if eid and ch.prev is not None:
                title, body = change_text(place.strip(), ch)
                _noti(conn, uid, eid, title, body, f"/item/{item_id}")
                n += 1
    return n


MORNING_BODY = "등기부·매각물건명세서가 어제와 같은지, 입찰표 금액을 한글로 읽어 보세요"
DEADLINE_KEYS = {"pay": "잔금", "tax": "취득세 신고", "order_deadline": "인도명령 신청"}


def make_bid_prep_alerts(conn: psycopg.Connection, *, morning: bool) -> int:
    """관심 물건 입찰 준비 알림. 아침: 오늘 입찰 / 저녁: 7일 뒤 입찰(명세서 공개)."""
    days, kind = (0, "bid_morning") if morning else (7, "spec_open")
    n = 0
    for uid, item_id, place, sale_date in conn.execute(
        """select w.user_id, i.item_id, coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, ''),
                  i.sale_date::text
           from app.watch_items w join core.items i using (item_id)
           where i.sale_date = current_date + %s""",
        (days,),
    ).fetchall():
        eid = _event(conn, uid, item_id, kind, None, sale_date)
        if not eid:
            continue
        if morning:
            title, body = f"오늘 입찰일 · {place.strip()}", MORNING_BODY
        else:
            title, body = (
                f"{place.strip()} 명세서가 나왔어요",
                "입찰 전에 떠안는 권리가 바뀌지 않았는지 다시 보세요",
            )
        link = f"/item/{item_id}/bid-day" if morning else f"/item/{item_id}"
        _noti(conn, uid, eid, title, body, link)
        n += 1
    return n


def make_deadline_alerts(conn: psycopg.Connection) -> int:
    """낙찰 받은 물건의 마감 3일 전 알림."""
    hol = [
        r[0] for r in conn.execute("select holiday_date from ref.holidays where checked").fetchall()
    ]
    today = conn.execute("select current_date").fetchone()[0]  # type: ignore[index]
    n = 0
    for uid, item_id, sale_date, pay_date in conn.execute(
        "select user_id, item_id, sale_date, pay_date from app.bid_results where outcome = 'won'"
    ).fetchall():
        rows = after_sale(sale_date, hol, pay_date=pay_date).value["rows"]
        for r in rows:
            if r["key"] not in DEADLINE_KEYS or (r["key"] == "pay" and pay_date):
                continue
            end = r["end"]
            if (date_from(end) - today).days != 3:
                continue
            eid = _event(conn, uid, item_id, f"deadline_{r['key']}", None, end)
            if eid:
                _noti(conn, uid, eid, f"{DEADLINE_KEYS[r['key']]} 마감이 3일 남았어요",
                      f"{short(date_from(end))}까지", "/me")  # fmt: skip
                n += 1
    return n


def date_from(s: str) -> date:
    return date.fromisoformat(s)


def send_pushes(conn: psycopg.Connection) -> int:
    key, subject = (
        os.getenv("VAPID_PRIVATE_KEY", "").strip(),
        os.getenv("VAPID_SUBJECT", "").strip(),
    )
    if not key:
        return 0
    from pywebpush import WebPushException, webpush

    sent = 0
    for nid, uid, title, body, link in conn.execute(
        "select noti_id, user_id, title, body, link from app.notifications where pushed_at is null "
        "and created_at > now() - interval '2 days' order by noti_id"
    ).fetchall():
        for sub_id, endpoint, p256dh, auth in conn.execute(
            "select sub_id, endpoint, p256dh, auth from app.push_subscriptions where user_id = %s",
            (uid,),
        ).fetchall():
            try:
                webpush(
                    {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                    json.dumps({"title": title, "body": body, "link": link, "tag": str(nid)}),
                    vapid_private_key=key,
                    vapid_claims={"sub": subject},
                )
                sent += 1
            except WebPushException as e:
                if e.response is not None and e.response.status_code in (404, 410):
                    conn.execute("delete from app.push_subscriptions where sub_id = %s", (sub_id,))
        conn.execute("update app.notifications set pushed_at = now() where noti_id = %s", (nid,))
    return sent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--morning", action="store_true", help="입찰일 아침 알림만")
    a = ap.parse_args()
    if a.morning:
        with connect() as conn, run(conn, "notify_morning", "입찰일 아침 알림") as job:
            m = make_bid_prep_alerts(conn, morning=True)
            conn.commit()
            p = 0 if a.no_push else send_pushes(conn)
            job.count = m
            print(f"입찰일 아침 {m} · 푸시 {p}")
        return
    with connect() as conn, run(conn, "notify", "알림") as job:
        s, w = make_search_alerts(conn), make_watch_alerts(conn)
        b, d = make_bid_prep_alerts(conn, morning=False), make_deadline_alerts(conn)
        conn.commit()
        p = 0 if a.no_push else send_pushes(conn)
        job.count = s + w + b + d
        print(f"조건 알림 {s} · 관심 알림 {w} · 명세서 {b} · 마감 {d} · 푸시 {p}")


if __name__ == "__main__":
    main()
