"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import {
  meApi,
  type Bid,
  type BidIn,
  type BidTodo,
  type Bids,
  type Mock,
  type WatchCard,
} from "@/lib/api/me";
import { PageHeader } from "@/components/layout/page-header";
import { useIsPc } from "@/lib/use-pc";
import { dday } from "@/lib/format";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.me;
const num = (s: string) => (s ? Number(s.replace(/[^0-9]/g, "")) || null : null);
const md = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;

// 결과 기록(RESULT-01): 결과 하나 고르고, 숫자는 아는 것만.
function RecordForm({ x, onSaved, token }: { x: BidTodo; onSaved: () => void; token: string }) {
  const [outcome, setOutcome] = useState<string | null>(null);
  const [f, setF] = useState({ my: "", win: "", second: "", n: "", pay: "" });
  const bid = outcome === "won" || outcome === "lost";
  const save = () => {
    const b: BidIn = {
      item_id: x.item_id,
      sale_date: x.sale_date,
      outcome: outcome!,
      my_bid_krw: num(f.my),
      winning_bid_krw: outcome === "won" ? num(f.my) : num(f.win),
      second_bid_krw: num(f.second),
      bidder_count: num(f.n),
      pay_date: f.pay || null,
    };
    meApi.saveBid(token, b).then(onSaved);
  };
  const input = (k: keyof typeof f, label: string, type = "text") => (
    <label style={{ display: "block", fontSize: 13, marginTop: 8 }}>
      <span className="sub" style={{ margin: 0 }}>
        {label}
      </span>
      <input
        type={type}
        inputMode={type === "text" ? "numeric" : undefined}
        value={f[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })}
        style={{
          width: "100%",
          fontSize: 16,
          padding: "8px 10px",
          border: "1px solid var(--line)",
          borderRadius: 8,
        }}
      />
    </label>
  );
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--line)" }}>
      <div style={{ fontWeight: 600 }}>
        {x.place} <span className="sub">· {md(x.sale_date)}</span>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
        {Object.entries(t.outcome).map(([k, v]) => (
          <button
            key={k}
            className={`chip ${outcome === k ? "green" : "gray"}`}
            style={{ minHeight: 36, border: 0 }}
            onClick={() => setOutcome(k)}
          >
            {v}
          </button>
        ))}
      </div>
      {bid && (
        <>
          {input("my", t.myBid)}
          {outcome === "lost" && input("win", t.winning)}
          {input("second", t.second)}
          {input("n", t.bidders)}
          {outcome === "won" && input("pay", t.payDate, "date")}
        </>
      )}
      {outcome && (
        <button className="btn primary" style={{ marginTop: 10, width: "100%" }} onClick={save}>
          {t.save}
        </button>
      )}
    </div>
  );
}

// 낙찰 받은 물건: 세 날짜 요약 + 마감만.
function WonCard({ b }: { b: Bid }) {
  const s = b.schedule!;
  const rng = (a: [string, string]) => `${md(a[0])} ~ ${md(a[1])}`;
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--line)" }}>
      <Link href={`/item/${b.item_id}`} style={{ fontWeight: 600, color: "inherit" }}>
        {b.place}
      </Link>
      <div className="sub" style={{ margin: 0 }}>
        {b.case_no} · {won(b.my_bid_krw)}
      </div>
      {[md(s.summary.pay), rng(s.summary.move_out), rng(s.summary.forced)].map((v, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 14,
            padding: "4px 0",
          }}
        >
          <span>{t.summary[i]}</span>
          <b>{v}</b>
        </div>
      ))}
      {s.pay_estimated && <div className="sub">{t.payGuess}</div>}
      <div style={{ marginTop: 6 }}>
        {s.rows
          .filter((r) => r.deadline && r.key !== "pay")
          .map((r) => (
            <div key={r.key} style={{ fontSize: 13, color: "var(--amber)" }}>
              ◆ {r.label} {r.short}
            </div>
          ))}
      </div>
    </div>
  );
}

export default function Me() {
  const { session, ready } = useSession();
  const [d, setD] = useState<Bids | null>(null);
  const [mocks, setMocks] = useState<Mock[]>([]);
  const [watch, setWatch] = useState<WatchCard[]>([]);
  const pc = useIsPc();
  const load = useCallback(() => {
    if (!session) return;
    meApi
      .watch(session.access_token)
      .then(setWatch)
      .catch(() => setWatch([]));
    meApi
      .bids(session.access_token)
      .then(setD)
      .catch(() => setD({ won: [], history: [], todo: [] }));
    meApi
      .mocks(session.access_token)
      .then(setMocks)
      .catch(() => setMocks([]));
  }, [session]);
  useEffect(load, [load]);

  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.tabs.me} />;
  const empty = d && !d.won.length && !d.history.length && !d.todo.length && !mocks.length;
  const dropMock = (id: number) => {
    setMocks((l) => l.filter((x) => x.mock_id !== id));
    meApi.removeMock(session.access_token, id).catch(() => {});
  };
  const upcoming = watch
    .filter((w) => w.d_day != null && w.d_day >= 0 && w.step !== "result" && w.step !== "after")
    .sort((x, y) => (x.d_day ?? 99) - (y.d_day ?? 99));
  const box = (title: string, hint: string | null, children: React.ReactNode, show: boolean) =>
    show || pc ? (
      <section className="section">
        <h2 style={{ fontSize: 16, margin: 0 }}>{title}</h2>
        {hint && (
          <p className="sub" style={{ margin: "4px 0 0" }}>
            {hint}
          </p>
        )}
        {children}
      </section>
    ) : null;

  const upcomingBox = box(
    t.upcoming,
    null,
    upcoming.length === 0 ? (
      <p className="sub">{t.upcomingEmpty}</p>
    ) : (
      upcoming.map((w) => (
        <Link
          key={w.item_id}
          href={
            w.d_day != null && w.d_day <= 1
              ? `/item/${encodeURIComponent(w.item_id)}/bid-day`
              : `/watch/${encodeURIComponent(w.item_id)}`
          }
          className="menu-row"
        >
          <span style={{ minWidth: 0 }}>
            <b style={{ color: w.d_day != null && w.d_day <= 7 ? "var(--red)" : "var(--amber)" }}>
              {dday(w.d_day)}
            </b>{" "}
            {w.sale_date?.slice(5).replace("-", "/")} · {w.place} {w.building ?? w.usage}
            <span className="sub" style={{ display: "block" }}>
              {copy.watch.steps[w.step]} · {w.court} {w.case_no}
            </span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))
    ),
    upcoming.length > 0,
  );

  const recordBox = box(
    t.recordTitle,
    d && d.todo.length > 0 ? t.todoHint : null,
    <>
      {d?.todo.map((x) => (
        <RecordForm key={x.item_id} x={x} token={session.access_token} onSaved={load} />
      ))}
      {d && d.todo.length === 0 && d.history.length === 0 && <p className="sub">{t.recordEmpty}</p>}
      {d && d.history.length > 0 && (
        <table className="pro-table" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>{t.cols.place}</th>
              <th>{t.cols.outcome}</th>
              <th>{t.cols.my}</th>
              <th>{t.cols.win}</th>
              <th>{t.cols.second}</th>
              <th>{t.cols.n}</th>
            </tr>
          </thead>
          <tbody>
            {d.history.map((b) => (
              <tr key={b.bid_id}>
                <td>{b.place}</td>
                <td>{t.outcome[b.outcome]}</td>
                <td>{won(b.my_bid_krw)}</td>
                <td>{won(b.winning_bid_krw)}</td>
                <td>{won(b.second_bid_krw)}</td>
                <td>{b.bidder_count != null ? `${b.bidder_count}명` : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>,
    Boolean(d && (d.todo.length > 0 || d.history.length > 0)),
  );

  const mockBox = box(
    copy.mock.notes,
    copy.mock.notesHint,
    <>
      {mocks.length === 0 && <p className="sub">{t.mockEmpty}</p>}
      {mocks.map((x) => (
        <div key={x.mock_id} style={{ padding: "10px 0", borderTop: "1px solid var(--line)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <Link
              href={`/item/${encodeURIComponent(x.item_id)}`}
              style={{ color: "inherit", fontWeight: 600, fontSize: 14 }}
            >
              {x.place} <span className="sub">{md(x.sale_date)}</span>
            </Link>
            <button
              className="chip gray"
              style={{ border: 0, minHeight: 28 }}
              onClick={() => dropMock(x.mock_id)}
            >
              {copy.mock.remove}
            </button>
          </div>
          <div className="sub">
            {x.decision === "skip" ? copy.mock.skip : `${copy.mock.amount} ${won(x.bid_krw ?? 0)}`}
            {x.max_krw ? ` · 상한 ${won(x.max_krw)}` : ""}
            {x.reason ? ` · ${x.reason}` : ""}
          </div>
          {x.review.map((line) => (
            <div key={line} style={{ fontSize: 14, marginTop: 2 }}>
              {line}
            </div>
          ))}
        </div>
      ))}
    </>,
    mocks.length > 0,
  );

  const wonBox = box(
    t.won,
    null,
    <>
      {d && d.won.length === 0 && <p className="sub">{t.wonEmpty}</p>}
      {d?.won.map((b) => (
        <WonCard key={b.bid_id} b={b} />
      ))}
    </>,
    Boolean(d && d.won.length > 0),
  );

  return (
    <main className="page">
      <PageHeader title={t.title} />
      {empty && !pc && (
        <section className="section">
          <p className="sub">{t.empty}</p>
        </section>
      )}
      {pc ? (
        <div className="pc-grid g-2x2">
          {upcomingBox}
          {recordBox}
          {mockBox}
          {wonBox}
        </div>
      ) : (
        <>
          {upcomingBox}
          {recordBox}
          {wonBox}
          {mockBox}
        </>
      )}
    </main>
  );
}
