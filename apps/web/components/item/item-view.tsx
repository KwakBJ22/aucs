"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DDay } from "@/components/dday";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import { CompareAdd, WsLink } from "@/components/item/actions";
import { Body } from "@/components/item/body";
import { answerOf } from "@/components/item/checklist";
import { InterestLine } from "@/components/item/interest-line";
import { ItemPhotos } from "@/components/item/item-photos";
import { OddsLine } from "@/components/item/next-round";
import { OutcomeBand } from "@/components/item/outcome-band";
import type { MyReg } from "@/components/item/registry";
import { SameHouse } from "@/components/item/same-house";
import { DOT, t } from "@/components/item/shared";
import type { ItemDetail } from "@/lib/api/items";
import { copyText } from "@/lib/copy-text";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

// 물건 상세 한 벌(11/8 — 예전엔 휴대폰·PC가 두 파일로 따로 그려 한쪽만 고치면 다른 쪽이 빠졌음).
// 내용은 하나, 배치만 다름: PC는 왼쪽 목차 · 가운데 질문을 모두 펼침 · 오른쪽 할 일,
// 휴대폰은 질문을 눌러 펼치고 할 일은 아래, 주 버튼은 화면 아래에 붙임.
export function ItemView({ d, reg, pc }: { d: ItemDetail; reg: MyReg; pc: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // 바로가기(/item/…#q-cost)로 들어오면 그 질문을 펼쳐 둠 — 접힌 채면 자리로 가도 내용이 안 보임
  useEffect(() => {
    const open1 = () => {
      const h = window.location.hash;
      if (h.startsWith("#q-") && h !== "#q-rounds") setOpen(h.slice(3));
    };
    open1();
    window.addEventListener("hashchange", open1);
    return () => window.removeEventListener("hashchange", open1);
  }, []);
  const id = encodeURIComponent(d.item_id);
  const closed = Boolean(d.outcome?.closed);
  const title = `${d.place} ${d.building ?? d.usage ?? ""}`.trim();

  // 휴대폰은 맨 위 줄에 매각기일이 있어 숫자 칸에서는 뺌
  const nums: [string, React.ReactNode][] = [
    ...(pc
      ? ([
          [
            t.pc.sale,
            <>
              <DDay d={d.d_day} /> <span className="nowrap">{d.sale_date ?? "-"}</span>
            </>,
          ],
        ] as [string, React.ReactNode][])
      : []),
    [t.pc.appraisal, won(d.appraisal_krw)],
    ...(closed
      ? []
      : ([
          [t.pc.deposit, won(d.deposit_krw)],
          [
            t.nextRound,
            d.next_round.min_price_krw ? (
              <>
                {won(d.next_round.min_price_krw)}
                {d.next_round.verified ? null : (
                  <span className="fs-xs fw-5 c-muted"> {t.nextRoundGuess}</span>
                )}
                <OddsLine odds={d.next_round.fail_odds} short />
              </>
            ) : (
              "-"
            ),
          ],
        ] as [string, React.ReactNode][])),
  ];

  const actions = (
    <aside className="section pc-sticky pc-actions">
      <div className="fs-base fw-7">{t.pc.actions}</div>
      {!closed && (
        <>
          <Link href={`/item/${id}/calc`} className="btn primary fs-base pc-only-flex">
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
  );

  return (
    <main className="page">
      <PageHeader
        title={pc ? title : ""}
        back="history"
        sub={
          pc ? (
            <span className="d-inline-flex gap-10 ai-center f-wrap">
              <span>
                {d.court} {d.case_no}
                {d.dept_name ? ` · ${d.dept_name}` : ""}
                {d.sale_place ? ` · ${d.sale_place}` : ""}
              </span>
              <button
                className="btn secondary sm"
                onClick={() => void copyText(d.case_no).then(() => setCopied(true))}
              >
                {copied ? t.pc.copied : t.pc.copy}
              </button>
            </span>
          ) : undefined
        }
        right={
          <div className="d-flex ai-center gap-8">
            <WsLink id={d.item_id} />
            <HeartButton id={d.item_id} />
          </div>
        }
      />
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      {d.d_day != null && d.d_day >= 0 && d.d_day <= 1 && (
        <Link href={`/item/${id}/bid-day`} className="btn soft sm mt-8">
          {copy.bidDay.title}
        </Link>
      )}

      <section className="section">
        {!pc && (
          <>
            <div className="sub">
              <DDay d={d.d_day} /> · {d.sale_date} · {d.court} {d.case_no}
            </div>
            <h1 className="fs-base fw-6 mt-4 mb-0">{title}</h1>
          </>
        )}
        <div className="item-price">
          {won(d.min_price_krw)}{" "}
          <span className="fs-md fw-5 c-muted d-inline-block">
            {copy.card.ofAppraisal} {d.min_rate}%
            {d.failed_count ? ` · ${copy.card.failed(d.failed_count)}` : ""}
          </span>
        </div>
        <div className="band-grid tiles mt-14">
          {nums.map(([k, v]) => (
            <div key={k} className={k === t.nextRound ? "tile-wide" : undefined}>
              <div className="sub m-0">{k}</div>
              <div className="fs-base fw-7 mt-2">{v}</div>
            </div>
          ))}
        </div>
        <OutcomeBand d={d} />
        <p className="fs-base fw-6 lh-15 mt-14 mb-0 mx-0">{d.verdict}</p>
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
        {pc && (
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
        )}
        <div className="kv-left">
          {d.questions.map((q) => {
            const shown = pc || open === q.key;
            return (
              <section key={q.key} id={`q-${q.key}`} className="section q-sec">
                <button
                  className={pc ? "q-head" : "q-head fold"}
                  disabled={pc}
                  aria-expanded={shown}
                  onClick={() => setOpen(open === q.key ? null : q.key)}
                >
                  <span className="toc-dot mt-6" style={{ background: DOT[q.tone] }} />
                  <span className="f-1">
                    <span className="sub d-block m-0 fs-sm">{q.title}</span>
                    <span className="q-answer">{answerOf(q, reg.u)}</span>
                  </span>
                </button>
                {shown && (
                  <div className="mt-12">
                    <Body q={q} d={d} />
                  </div>
                )}
              </section>
            );
          })}
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
            {!closed && <OddsLine odds={d.next_round.fail_odds} />}
          </section>
          <p className="sub fs-xs">{t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}</p>
        </div>
        {actions}
      </div>

      {/* 휴대폰: 주 버튼 하나를 화면 아래에 붙임(08-look 5절) */}
      {!pc && (d.d_day ?? -1) >= 0 && (
        <div className="cta-bar">
          <Link href={`/item/${id}/calc`} className="btn primary">
            {t.bidTry}
          </Link>
        </div>
      )}
    </main>
  );
}
