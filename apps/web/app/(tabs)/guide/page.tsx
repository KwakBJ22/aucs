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
      <div className="sub fs-base mt-0 mb-8 mx-4">{t.sub}</div>

      <section className="section">
        <h2>{t.stepsTitle}</h2>
        {t.steps.map(([name, body, href, where], i) => (
          <div key={name} className="d-flex gap-12 py-12 px-0">
            <div
              className="r-14 bg-blue-soft c-blue-text fw-7 d-flex ai-center jc-center f-none"
              style={{ width: 28, height: 28 }}
            >
              {i + 1}
            </div>
            <div>
              <div className="fw-7">{name}</div>
              <div className="fs-md mt-2">{body}</div>
              {href ? (
                <Link href={href} className="sub c-blue">
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
              className="w-full d-flex jc-between ai-center b-0 bg-none py-12 px-0 fs-base fw-6 ta-left mh-44"
            >
              {w} <span className="sub">{open === w ? "⌃" : "⌄"}</span>
            </button>
            {open === w && <div className="fs-md pb-12">{body}</div>}
          </div>
        ))}
      </section>

      <section className="section">
        <h2>{t.mistakesTitle}</h2>
        {t.mistakes.map((m) => (
          <div key={m} className="fs-md py-8 px-0">
            ◆ {m}
          </div>
        ))}
      </section>
      <div className="sub my-0 mx-4">{t.note}</div>
    </main>
  );
}
