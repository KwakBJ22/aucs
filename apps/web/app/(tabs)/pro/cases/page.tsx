"use client";

import { Delayed, SkRows } from "@/components/skeleton";
import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchCase, fetchCases, type CaseDetail, type CaseRow } from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { dday, todayKst, won } from "@/lib/format";
import { PrintHead } from "@/components/print-head";

const t = copy.proCases;
const DOT = { high: "var(--red)", mid: "var(--orange)", low: "var(--faint)" } as const;

function Detail({ d }: { d: CaseDetail }) {
  const [all, setAll] = useState(false);
  const ev = d.events.filter((e) => all || e.importance !== "low" || e.after_deadline);
  return (
    <div>
      <PrintHead title={t.printBrand} sub={`${d.court} ${d.case_no}`} date={todayKst()} />
      <div className="sub">
        {d.court} {d.dept}
      </div>
      <div className="d-flex jc-between ai-center gap-8">
        <h2 className="mt-2 mb-6 mx-0">{d.case_no}</h2>
        <button
          className="btn primary no-print py-0 px-14 fs-md"
          style={{ width: "auto", height: 36 }}
          onClick={() => window.print()}
        >
          {t.report}
        </button>
      </div>
      <div className="band-grid four mt-6 mb-12 mx-0">
        {[
          [t.cards.progress, d.progress ?? t.cards.normal],
          [t.cards.docs, `${d.events.length}건`],
          [t.cards.high, `${d.events.filter((e) => e.importance === "high").length}건`],
          [t.cards.late, `${d.events.filter((e) => e.after_deadline).length}건`],
        ].map(([k, v]) => (
          <div key={k} className="bg-bg r-12 py-10 px-12">
            <div className="sub m-0">{k}</div>
            <div className="fs-base fw-7">{v}</div>
          </div>
        ))}
      </div>
      {d.progress && (
        <div className="chip orange mb-8">
          ◆ {t.progress}: {d.progress}
        </div>
      )}
      {d.claim_deadline && <div className="sub">{t.deadline(d.claim_deadline)}</div>}
      {d.items.map((i) => (
        <Link
          key={i.item_id}
          prefetch={false}
          href={`/item/${encodeURIComponent(i.item_id)}`}
          className="d-block fs-md py-6 px-0"
        >
          {i.item_no}. {i.usage_name} · {won(i.min_price_krw)}{" "}
          <span className="sub">
            {i.sale_date?.slice(5)} {dday(i.d_day)} ›
          </span>
        </Link>
      ))}
      <div className="d-flex f-wrap gap-4 my-10 mx-0">
        {d.counts.map(([c, n]) => (
          <span key={c} className="chip gray">
            {c} {n}
          </span>
        ))}
      </div>
      <div className="d-flex jc-between ai-center">
        <b className="fs-base">{t.flow}</b>
        <button className="chip gray b-0 mh-30" onClick={() => setAll(!all)}>
          {all ? t.importantOnly : t.showAll(d.events.length)}
        </button>
      </div>
      {ev.map((e, i) => (
        <div key={i} className="d-flex gap-8 py-6 px-0 fs-md">
          <span className="sub nowrap" style={{ minWidth: 74 }}>
            {e.event_date}
          </span>
          <span
            className="r-4 mt-6 f-none"
            style={{ width: 8, height: 8, background: DOT[e.importance] }}
          />
          <span>
            <b>{e.category}</b>
            {e.after_deadline && <span className="c-red"> · {t.late}</span>}
            <span className="sub d-block">
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
      <div className="sub mb-8 no-print">{t.sub}</div>
      <div className="d-flex gap-6 f-wrap mb-8 no-print">
        <button
          className={`pill${!cat ? " on" : ""}`}

          onClick={() => go({ category: "" })}
        >
          {t.all}
        </button>
        {cats.map((c) => (
          <button
            key={c}
            className={`pill${cat === c ? " on" : ""}`}

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
          className="fs-md py-4 px-8 b-0 r-14 bg-panel c-text"
        />
      </div>
      <div className="pc-grid g-26-74">
        <section className="section m-0 no-print">
          {list === null && (
            <Delayed>
              <SkRows n={8} />
            </Delayed>
          )}
          {list?.length === 0 && <div className="sub">{t.empty}</div>}
          {list?.map((c) => (
            <button
              key={c.case_id}
              onClick={() => go({ id: c.case_id })}
              className="d-block w-full ta-left b-0 r-10 p-8"
              style={{ background: c.case_id === id ? "var(--blue-soft)" : "none" }}
            >
              <div className="sub">
                {c.court} {c.case_no} · {dday(c.d_day)}
              </div>
              <div className="fs-md fw-6">{c.place}</div>
              <div className="fs-xs c-orange">
                {[...c.flags, ...(c.late > 0 ? [t.lateN(c.late)] : [])].join(" · ")}
              </div>
            </button>
          ))}
        </section>
        <section className="section m-0 print-area">
          {d ? <Detail d={d} /> : <div className="sub">{t.pick}</div>}
        </section>
      </div>
      <div className="sub mt-8 no-print">{t.note}</div>
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
