"use client";

import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchCase, fetchCases, type CaseDetail, type CaseRow } from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

const t = copy.proCases;
const DOT = { high: "var(--red)", mid: "var(--orange)", low: "var(--faint)" } as const;

function Detail({ d }: { d: CaseDetail }) {
  const [all, setAll] = useState(false);
  const ev = d.events.filter((e) => all || e.importance !== "low" || e.after_deadline);
  return (
    <div>
      <div className="sub">
        {d.court} {d.dept}
      </div>
      <div
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}
      >
        <h2 style={{ margin: "2px 0 6px" }}>{d.case_no}</h2>
        <button
          className="btn primary no-print"
          style={{ width: "auto", height: 36, padding: "0 14px", fontSize: 14 }}
          onClick={() => window.print()}
        >
          {t.report}
        </button>
      </div>
      <div className="band-grid four" style={{ margin: "6px 0 12px" }}>
        {[
          [t.cards.progress, d.progress ?? t.cards.normal],
          [t.cards.docs, `${d.events.length}건`],
          [t.cards.high, `${d.events.filter((e) => e.importance === "high").length}건`],
          [t.cards.late, `${d.events.filter((e) => e.after_deadline).length}건`],
        ].map(([k, v]) => (
          <div key={k} style={{ background: "var(--bg)", borderRadius: 12, padding: "10px 12px" }}>
            <div className="sub" style={{ margin: 0 }}>
              {k}
            </div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{v}</div>
          </div>
        ))}
      </div>
      {d.progress && (
        <div className="chip orange" style={{ marginBottom: 8 }}>
          ◆ {t.progress}: {d.progress}
        </div>
      )}
      {d.claim_deadline && <div className="sub">{t.deadline(d.claim_deadline)}</div>}
      {d.items.map((i) => (
        <Link
          key={i.item_id}
          href={`/item/${encodeURIComponent(i.item_id)}`}
          style={{
            display: "block",
            fontSize: 14,
            padding: "6px 0",
          }}
        >
          {i.item_no}. {i.usage_name} · {won(i.min_price_krw)}{" "}
          <span className="sub">
            {i.sale_date?.slice(5)} {dday(i.d_day)} ›
          </span>
        </Link>
      ))}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, margin: "10px 0" }}>
        {d.counts.map(([c, n]) => (
          <span key={c} className="chip gray">
            {c} {n}
          </span>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <b style={{ fontSize: 15 }}>{t.flow}</b>
        <button
          className="chip gray"
          style={{ border: 0, minHeight: 30 }}
          onClick={() => setAll(!all)}
        >
          {all ? t.importantOnly : t.showAll(d.events.length)}
        </button>
      </div>
      {ev.map((e, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            gap: 8,
            padding: "7px 0",
            fontSize: 14,
          }}
        >
          <span className="sub" style={{ whiteSpace: "nowrap", minWidth: 74 }}>
            {e.event_date}
          </span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 4,
              background: DOT[e.importance],
              marginTop: 6,
              flexShrink: 0,
            }}
          />
          <span>
            <b>{e.category}</b>
            {e.after_deadline && <span style={{ color: "var(--red)" }}> · {t.late}</span>}
            <span className="sub" style={{ display: "block" }}>
              {e.kind} {e.text_masked}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function Cases() {
  const router = useRouter();
  const sp = useSearchParams();
  const cat = sp.get("category") ?? "";
  const id = sp.get("id") ?? "";
  const sq = sp.get("q") ?? "";
  const [list, setList] = useState<CaseRow[] | null>(null);
  const [cats, setCats] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [d, setD] = useState<CaseDetail | null>(null);

  const go = (patch: Record<string, string>) => {
    const p = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    router.replace(`/pro/cases?${p}`);
  };
  // 사건을 고를 때(주소의 id만 바뀔 때)는 목록을 다시 부르지 않음(10/27)
  useEffect(() => {
    let stale = false;
    setList(null);
    fetchCases(cat || undefined, sq || undefined)
      .then((r) => {
        if (stale) return;
        setList(r.cases);
        setCats(r.categories);
      })
      .catch(() => !stale && setList([]));
    return () => {
      stale = true;
    };
  }, [cat, sq]);
  useEffect(() => {
    if (!id) return setD(null);
    fetchCase(id)
      .then(setD)
      .catch(() => setD(null));
  }, [id]);

  return (
    <main className="page pro-page">
      <PageHeader title={t.title} />
      <div className="sub" style={{ marginBottom: 8 }}>
        {t.sub}
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
        <button
          className={`chip ${!cat ? "green" : "gray"}`}
          style={{ border: 0, minHeight: 30 }}
          onClick={() => go({ category: "" })}
        >
          {t.all}
        </button>
        {cats.map((c) => (
          <button
            key={c}
            className={`chip ${cat === c ? "green" : "gray"}`}
            style={{ border: 0, minHeight: 30 }}
            onClick={() => go({ category: c })}
          >
            {c}
          </button>
        ))}
        <input
          placeholder={t.search}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go({ q })}
          style={{
            fontSize: 14,
            padding: "4px 8px",
            border: 0,
            borderRadius: 14,
            background: "var(--panel)",
            color: "var(--text)",
          }}
        />
      </div>
      <div className="pc-grid g-26-74">
        <section className="section" style={{ margin: 0 }}>
          {list === null && <div className="sub">{copy.pro.loading}</div>}
          {list?.length === 0 && <div className="sub">{t.empty}</div>}
          {list?.map((c) => (
            <button
              key={c.case_id}
              onClick={() => go({ id: c.case_id })}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                border: 0,
                background: c.case_id === id ? "var(--blue-soft)" : "none",
                borderRadius: 10,
                padding: "8px 8px",
              }}
            >
              <div className="sub">
                {c.court} {c.case_no} · {dday(c.d_day)}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{c.place}</div>
              <div style={{ fontSize: 12, color: "var(--orange)" }}>
                {[...c.flags, ...(c.late > 0 ? [t.lateN(c.late)] : [])].join(" · ")}
              </div>
            </button>
          ))}
        </section>
        <section className="section" style={{ margin: 0 }}>
          {d ? <Detail d={d} /> : <div className="sub">{t.pick}</div>}
        </section>
      </div>
      <div className="sub" style={{ marginTop: 8 }}>
        {t.note}
      </div>
    </main>
  );
}

export default function ProCasesPage() {
  return (
    <Suspense>
      <Cases />
    </Suspense>
  );
}
