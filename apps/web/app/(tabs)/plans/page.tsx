"use client";

import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { copy } from "@/lib/copy.ko";

const t = copy.plans;

// 이용권 고르기(PAY-01). 금액·개수는 임시값(결정 #4). 결제는 사업자등록·토스페이먼츠 계약 뒤 열림.
export default function Plans() {
  const [yearly, setYearly] = useState(false);
  const [pick, setPick] = useState<string>("personal");
  return (
    <main className="page">
      <PageHeader title={t.title} back="/more" />
      <div className="seg" role="tablist" style={{ maxWidth: 420 }}>
        <button
          role="tab"
          aria-selected={!yearly}
          className={!yearly ? "on" : ""}
          onClick={() => setYearly(false)}
        >
          {t.monthly}
        </button>
        <button
          role="tab"
          aria-selected={yearly}
          className={yearly ? "on" : ""}
          onClick={() => setYearly(true)}
        >
          {t.yearly}
        </button>
      </div>
      <div className="pc-grid g-4" style={{ marginTop: 12 }}>
        {t.list.map((p) => (
          <section
            key={p.key}
            className="section"
            style={{ outline: pick === p.key ? "2px solid var(--blue)" : undefined, marginTop: 0 }}
            onClick={() => setPick(p.key)}
          >
            <div
              style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}
            >
              <h2>{p.name}</h2>
              {p.tag && <span className="chip green">{p.tag}</span>}
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, marginTop: 4 }}>
              {yearly && p.yearly ? p.yearly : p.price}
              <span className="sub" style={{ fontSize: 14, fontWeight: 400 }}>
                {" "}
                {yearly && p.yearly ? t.perYear : p.per}
              </span>
            </div>
            <div className="sub">{p.what}</div>
            {p.items.map((x) => (
              <div key={x} className="line-row" style={{ fontSize: 14 }}>
                <span>{x}</span>
                <b style={{ color: "var(--green)" }}>✓</b>
              </div>
            ))}
            {p.key === "one" ? (
              <Link
                href="/find"
                className="btn"
                style={{ background: "var(--gray-chip)", height: 46, fontSize: 15, marginTop: 12 }}
              >
                {t.toFind}
              </Link>
            ) : p.key !== "free" ? (
              <button
                className="btn primary"
                style={{ height: 46, fontSize: 15, marginTop: 12 }}
                disabled
                title={t.payLater}
              >
                {p.cta}
              </button>
            ) : null}
          </section>
        ))}
      </div>
      <section className="section">
        <h2>{t.refundTitle}</h2>
        {t.refund.map((x) => (
          <div key={x} className="sub" style={{ padding: "4px 0" }}>
            {x}
          </div>
        ))}
        <div className="sub" style={{ marginTop: 8, fontWeight: 600 }}>
          {t.payLater}
        </div>
      </section>
    </main>
  );
}
