"use client";

import { useState } from "react";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import type { ItemDetail } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import Link from "next/link";
import { WsLink, CompareAdd } from "@/components/item/actions";
import { Body } from "@/components/item/body";
import { answerOf } from "@/components/item/checklist";
import type { MyReg } from "@/components/item/registry";
import { t, DOT } from "@/components/item/shared";
import { SameHouse } from "@/components/item/same-house";
import { ItemPhotos } from "@/components/item/item-photos";
import { OutcomeBand } from "@/components/item/outcome-band";
import { InterestLine } from "@/components/item/interest-line";

export function ItemPc({ d, reg }: { d: ItemDetail; reg: MyReg }) {
  const [copied, setCopied] = useState(false);
  const id = encodeURIComponent(d.item_id);
  const urgent = d.d_day != null && d.d_day <= 7;
  const stats: [string, React.ReactNode][] = [
    [
      t.pc.sale,
      <>
        <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>{dday(d.d_day)}</b>{" "}
        {d.sale_date ?? "-"}
      </>,
    ],
    [t.pc.appraisal, won(d.appraisal_krw)],
    [
      t.pc.min,
      <>
        {won(d.min_price_krw)} <span className="sub">{d.min_rate}%</span>
      </>,
    ],
    [t.pc.failed, d.failed_count ? copy.card.failed(d.failed_count) : t.pc.none],
    ...(d.outcome?.closed
      ? []
      : ([
          [
            t.nextRound,
            d.next_round.min_price_krw
              ? `${won(d.next_round.min_price_krw)}${d.next_round.verified ? "" : ` ${t.nextRoundGuess}`}`
              : "-",
          ],
          [t.pc.deposit, won(d.deposit_krw)],
        ] as [string, React.ReactNode][])),
  ];
  return (
    <main className="page">
      <PageHeader
        title={`${d.place} ${d.building ?? d.usage ?? ""}`}
        sub={
          <span className="d-inline-flex gap-10 ai-center f-wrap">
            <span>
              {d.court} {d.case_no}
              {d.dept_name ? ` · ${d.dept_name}` : ""}
              {d.sale_place ? ` · ${d.sale_place}` : ""}
            </span>
            <button
              className="chip gray b-0 mh-28"
              onClick={() => {
                navigator.clipboard?.writeText(d.case_no).then(() => setCopied(true));
              }}
            >
              {copied ? t.pc.copied : t.pc.copy}
            </button>
          </span>
        }
        right={
          <div className="d-flex ai-center gap-8">
            <WsLink id={d.item_id} />
            <HeartButton id={d.item_id} />
          </div>
        }
      />
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      <section className="section">
        <div className="band-grid">
          {stats.map(([k, v]) => (
            <div key={k}>
              <div className="sub m-0">{k}</div>
              <div className="fs-lg fw-7 mt-2">{v}</div>
            </div>
          ))}
        </div>
        <OutcomeBand d={d} />
        <p className="fs-lg fw-6 lh-15 mt-14 mb-0 mx-0">{d.verdict}</p>
        <InterestLine v={d.interest} />
        <SameHouse list={d.same_house} />
        <ItemPhotos list={d.photos} />
        {d.tags.length > 0 && (
          <div className="d-flex gap-6 f-wrap mt-10">
            {d.tags.map((x) => (
              <span key={x.label} className={`chip ${x.ok ? "green" : "gray"}`}>
                {x.label}
              </span>
            ))}
          </div>
        )}
      </section>
      <div className="pc-grid g-14-62-24">
        <nav className="section pc-sticky toc" aria-label={t.pc.toc}>
          {d.questions.map((q) => (
            <a key={q.key} href={`#q-${q.key}`}>
              <span className="toc-dot" style={{ background: DOT[q.tone] }} />
              {q.title}
            </a>
          ))}
          <a href="#q-rounds">
            <span className="toc-dot bg-faint" />
            {t.rounds}
          </a>
        </nav>
        <div className="kv-left">
          {d.questions.map((q) => (
            <section key={q.key} id={`q-${q.key}`} className="section q-sec">
              <div className="sub m-0">{q.title}</div>
              <h2 className="d-flex gap-8 ai-baseline mt-4 mb-12 mx-0">
                <span className="toc-dot" style={{ background: DOT[q.tone] }} />
                {answerOf(q, reg.u)}
              </h2>
              <Body q={q} d={d} />
            </section>
          ))}
          <section id="q-rounds" className="section q-sec">
            <h2>{t.rounds}</h2>
            <table className="pro-table mt-8">
              <thead>
                <tr>
                  <th>{t.pc.date}</th>
                  <th>{t.pc.min}</th>
                  <th>{t.pc.result}</th>
                </tr>
              </thead>
              <tbody>
                {d.rounds.map((r) => (
                  <tr key={r.sale_date}>
                    <td>{r.sale_date}</td>
                    <td>{won(r.min_price_krw)}</td>
                    <td>{r.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <p className="sub fs-xs">{t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}</p>
        </div>
        <aside className="section pc-sticky pc-actions">
          <div className="fs-base fw-7">{t.pc.actions}</div>
          {!d.outcome?.closed && (
            <>
              <Link
                href={`/item/${id}/calc`}
                className="btn primary fs-base"
                style={{ height: 46 }}
              >
                {t.bidTry}
              </Link>
              <Link href={`/item/${id}/bid-sheet`} className="pc-act">
                {copy.bidSheet.title}
              </Link>
              <Link href={`/item/${id}/bid-day`} className="pc-act">
                {copy.bidDay.title}
              </Link>
            </>
          )}
          <CompareAdd id={d.item_id} />
          <Link href="/pro/market" className="pc-act">
            {t.pc.market}
          </Link>
          <Link href={`/item/${id}/report`} className="pc-act">
            {copy.report.open}
          </Link>
          <div className="sub fs-xs">
            {t.pc.basis(d.computed_at ? d.computed_at.slice(0, 16).replace("T", " ") : "-")}
          </div>
        </aside>
      </div>
    </main>
  );
}
