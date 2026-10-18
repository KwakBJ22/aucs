"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import { meApi, type Bid, type BidIn, type BidTodo, type Bids } from "@/lib/api/me";
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
  const load = useCallback(() => {
    if (session)
      meApi
        .bids(session.access_token)
        .then(setD)
        .catch(() => setD({ won: [], history: [], todo: [] }));
  }, [session]);
  useEffect(load, [load]);

  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.tabs.me} />;
  const empty = d && !d.won.length && !d.history.length && !d.todo.length;
  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
      </div>
      {empty && (
        <section className="section">
          <p className="sub">{t.empty}</p>
        </section>
      )}
      {d && d.todo.length > 0 && (
        <section className="section">
          <h2 style={{ fontSize: 16, margin: 0 }}>{t.todo}</h2>
          <p className="sub" style={{ margin: "4px 0 0" }}>
            {t.todoHint}
          </p>
          {d.todo.map((x) => (
            <RecordForm key={x.item_id} x={x} token={session.access_token} onSaved={load} />
          ))}
        </section>
      )}
      {d && d.won.length > 0 && (
        <section className="section">
          <h2 style={{ fontSize: 16, margin: 0 }}>{t.won}</h2>
          {d.won.map((b) => (
            <WonCard key={b.bid_id} b={b} />
          ))}
        </section>
      )}
      {d && d.history.length > 0 && (
        <section className="section">
          <h2 style={{ fontSize: 16, margin: 0 }}>{t.history}</h2>
          {d.history.map((b) => (
            <div key={b.bid_id} style={{ fontSize: 14, padding: "6px 0" }}>
              {b.place} · {t.outcome[b.outcome]}
              {b.bidder_count != null && ` · ${b.bidder_count}명`}
              {b.winning_bid_krw && ` · 낙찰 ${won(b.winning_bid_krw)}`}
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
