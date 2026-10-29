"use client";

import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";
import { useState } from "react";
import { copy } from "@/lib/copy.ko";

const t = copy.guide;

// 초보 안내: 진행 순서 6단계(옥스에서 어디서 하는지) · 꼭 알아야 할 말(눌러서 펼침) · 많이 하는 실수
export default function Guide() {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <main className="page">
      <PageHeader title={t.title} back="/more" />
      <div className="sub" style={{ fontSize: 15, margin: "0 4px 8px" }}>
        {t.sub}
      </div>

      <section className="section">
        <h2>{t.stepsTitle}</h2>
        {t.steps.map(([name, body, href, where], i) => (
          <div
            key={name}
            style={{
              display: "flex",
              gap: 12,
              padding: "12px 0",
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 14,
                background: "var(--blue-soft)",
                color: "var(--blue-text)",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              {i + 1}
            </div>
            <div>
              <div style={{ fontWeight: 700 }}>{name}</div>
              <div style={{ fontSize: 14, marginTop: 2 }}>{body}</div>
              {href ? (
                <Link href={href} className="sub" style={{ color: "var(--blue)" }}>
                  {where} ›
                </Link>
              ) : (
                <span className="sub">{where}</span>
              )}
            </div>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{t.wordsTitle}</h2>
        {t.words.map(([w, body]) => (
          <div key={w} style={{}}>
            <button
              onClick={() => setOpen(open === w ? null : w)}
              style={{
                width: "100%",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                border: 0,
                background: "none",
                padding: "12px 0",
                fontSize: 15,
                fontWeight: 600,
                textAlign: "left",
                minHeight: 44,
              }}
            >
              {w} <span className="sub">{open === w ? "⌃" : "⌄"}</span>
            </button>
            {open === w && <div style={{ fontSize: 14, paddingBottom: 12 }}>{body}</div>}
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{t.mistakesTitle}</h2>
        {t.mistakes.map((m) => (
          <div key={m} style={{ fontSize: 14, padding: "8px 0" }}>
            ◆ {m}
          </div>
        ))}
      </section>
      <div className="sub" style={{ margin: "0 4px" }}>
        {t.note}
      </div>
    </main>
  );
}
