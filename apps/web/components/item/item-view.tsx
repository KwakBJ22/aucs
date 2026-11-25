"use client";

import Link from "next/link";
import { Fragment, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { DDay } from "@/components/dday";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import { CompareAdd, WsLink } from "@/components/item/actions";
import { Body } from "@/components/item/body";
import { CapLine } from "@/components/item/cap-line";
import { answerOf } from "@/components/item/checklist";
import { InterestLine } from "@/components/item/interest-line";
import { SameBuilding } from "@/components/item/same-building";
import { ItemPhotos } from "@/components/item/item-photos";
import { OriginalLink } from "@/components/item/appraisal";
import { ReportBox } from "@/components/item/doc-sheet";
import { OddsLine } from "@/components/item/next-round";
import { OutcomeBand } from "@/components/item/outcome-band";
import type { MyReg } from "@/components/item/registry";
import { SameHouse } from "@/components/item/same-house";
import { DOT, t, DocCtx } from "@/components/item/shared";
import type { ItemDetail } from "@/lib/api/items";
import { copyText } from "@/lib/copy-text";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

// 물건 상세 한 벌(11/8 — 예전엔 휴대폰·PC가 두 파일로 따로 그려 한쪽만 고치면 다른 쪽이 빠졌음).
// 내용은 하나, 배치만 다름: PC는 왼쪽 목차 · 가운데 질문을 모두 펼침 · 오른쪽 할 일,
// 휴대폰은 질문을 눌러 펼치고 할 일은 아래, 주 버튼은 화면 아래에 붙임.
export function ItemView({ d, reg, pc }: { d: ItemDetail; reg: MyReg; pc: boolean }) {
  // 휴대폰은 「무엇을 사나」를 펼친 채 시작(11/11 대표님)
  const [open, setOpen] = useState<string | null>(
    d.questions.some((q) => q.key === "buy") ? "buy" : null,
  );
  // 질문을 누르면 위 질문이 접히며 내용이 빠져 누른 줄이 위로 휙 올라가던 것(11/11):
  // 누른 줄을 손가락 아래 그 자리에 붙잡아 둠
  const pin = useRef<{ el: HTMLElement; top: number } | null>(null);
  useLayoutEffect(() => {
    const p = pin.current;
    pin.current = null;
    if (!p) return;
    const moved = p.el.getBoundingClientRect().top - p.top;
    if (moved) window.scrollBy(0, moved);
  }, [open]);
  const [copied, setCopied] = useState(false);
  const openDoc = useContext(DocCtx);
  const verdict = (
    <Verdict text={d.verdict} tone={d.questions.find((q) => q.key === "hold")?.tone} />
  );
  // 휴대폰 「바로 꺼내 보기」(11/23 M-Detail): 칩을 누르면 그 칸이 든 질문을 펼치고, 그려진 뒤 그 칸으로
  const [jump, setJump] = useState<string | null>(null);
  useEffect(() => {
    if (!jump) return;
    const el = document.getElementById(jump);
    if (el instanceof HTMLDetailsElement) el.open = true;
    el?.scrollIntoView({ block: "start" });
    setJump(null);
  }, [jump, open]);
  // PC 왼쪽 목차: 지금 보이는 질문(11/22 디자인 — 연파랑 판)
  const [onQ, setOnQ] = useState(0);
  useEffect(() => {
    if (!pc) return;
    const keys = [...d.questions.map((q) => `q-${q.key}`), "q-rounds"];
    const pick = () => {
      let cur = 0;
      keys.forEach((k, i) => {
        const el = document.getElementById(k);
        if (el && el.getBoundingClientRect().top < 200) cur = i;
      });
      setOnQ(cur);
    };
    pick();
    window.addEventListener("scroll", pick, { passive: true });
    return () => window.removeEventListener("scroll", pick);
  }, [pc, d.questions]);
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
    <main className="page wide">
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
              {/* 입찰일 아침(11/22 디자인 — 사건 줄 끝에) */}
              {d.d_day != null && d.d_day >= 0 && d.d_day <= 1 && (
                <Link href={`/item/${id}/bid-day`} className="chip-link">
                  {copy.bidDay.title}
                </Link>
              )}
            </span>
          ) : undefined
        }
        right={
          <div className="d-flex ai-center gap-8">
            <WsLink id={d.item_id} />
            <HeartButton id={d.item_id} inline />
          </div>
        }
      />
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      {!pc && d.d_day != null && d.d_day >= 0 && d.d_day <= 1 && (
        <Link href={`/item/${id}/bid-day`} className="bd-chip">
          {copy.bidDay.title}
        </Link>
      )}

      <section className="section item-top">
        {!pc && (
          <>
            <div className="sub">
              <DDay d={d.d_day} /> · {d.sale_date} · {d.court} {d.case_no}
            </div>
            <h1 className="item-title">{title}</h1>
          </>
        )}
        <div className="item-price">
          {won(d.min_price_krw)}{" "}
          <span className="item-price-sub">
            {pc ? t.panel.priceLabel(d.min_rate) : `${copy.card.ofAppraisal} ${d.min_rate}%`}
            {d.failed_count ? ` · ${copy.card.failedOf(d.failed_count, d.price_round)}` : ""}
          </span>
        </div>
        {!closed && <CapLine id={d.item_id} minPrice={d.min_price_krw} />}
        {/* 휴대폰(11/23 M-Detail): 판정 판을 값 바로 아래 · PC 는 숫자 칸 아래 그대로 */}
        {!pc && verdict}
        <div className="band-grid tiles mt-14">
          {nums.map(([k, v]) => (
            <div key={k} className={k === t.nextRound ? "tile-wide" : undefined}>
              <div className="sub m-0">{k}</div>
              <div className="tile-v">{v}</div>
            </div>
          ))}
        </div>
        <OutcomeBand d={d} />
        {pc && verdict}
        {!closed && d.court_interest && d.court_interest.n > 0 && (
          <div className="sub fs-sm mt-6">
            {copy.interest.court(d.court_interest.n, d.court_interest.at)}
          </div>
        )}
        <InterestLine v={d.interest} />
        <SameHouse list={d.same_house} />
        {!closed && <SameBuilding v={d.same_building} />}
        <ItemPhotos list={d.photos} />
        <div className="item-tags">
          {d.tags.map((x) => (
            <span key={x.label} className={`chip ${x.ok ? "green" : "gray"}`}>
              {x.label}
            </span>
          ))}
          {/* 감정평가서(11/11 대표님 — 어디서 보는지 안 보였음): 서류 줄 끝에 바로 */}
          <OriginalLink pdf={d.appraisal?.pdf_url} court={d.court} caseNo={d.case_no} compact />
          {pc && <span className="sub">{t.panel.legend}</span>}
        </div>
      </section>
      {!pc && (
        <div className="q-jump-m">
          <p className="q-jump-t">{t.panel.jump}</p>
          <div className="m-chips quiet-scroll">
            {t.panel.jumps.map(([k, label]) => (
              <button
                key={k}
                className="fc-chip"
                onClick={() => {
                  const q = JUMP_Q[k];
                  if (q && d.questions.some((x) => x.key === q)) setOpen(q);
                  setJump(k);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="pc-grid g-14-62-24">
        {pc && (
          <div className="pc-sticky item-nav">
            {/* 11/22 디자인: 질문 이름 아래 답 한 줄 · 지금 보는 질문은 연파랑 판 */}
            <nav className="section toc q-toc" aria-label={t.pc.toc}>
              {d.questions.map((q, i) => (
                <a key={q.key} href={`#q-${q.key}`} className={i === onQ ? "on" : ""}>
                  <span className="q-toc-t">
                    <span className="toc-dot" style={{ background: DOT[q.tone] }} />
                    {q.title}
                  </span>
                  <span className="q-toc-a">{answerOf(q, reg.u)}</span>
                </a>
              ))}
              <a href="#q-rounds" className={onQ === d.questions.length ? "on" : ""}>
                <span className="q-toc-t">
                  <span className="toc-dot bg-faint" />
                  {t.rounds}
                </span>
                {d.rounds[0] && (
                  <span className="q-toc-a">
                    {d.rounds[d.rounds.length - 1]?.sale_date.slice(5).replace("-", "/")}{" "}
                    {d.rounds[d.rounds.length - 1]?.result}
                  </span>
                )}
              </a>
            </nav>
            <div className="section q-jump">
              <p className="q-jump-t">{t.panel.jump}</p>
              <div className="d-flex f-wrap gap-6">
                {t.panel.jumps.map(([k, label]) => (
                  <a key={k} href={`#${k}`}>
                    {label}
                  </a>
                ))}
              </div>
            </div>
          </div>
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
                  onClick={(e) => {
                    pin.current = {
                      el: e.currentTarget,
                      top: e.currentTarget.getBoundingClientRect().top,
                    };
                    setOpen(open === q.key ? null : q.key);
                  }}
                >
                  <span className="toc-dot mt-6" style={{ background: DOT[q.tone] }} />
                  <span className="f-1">
                    <span className="q-label">{q.title}</span>
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
            <h2 className={pc ? "q-label" : undefined}>{t.rounds}</h2>
            {/* PC(11/22 디자인): 이번 기일 · 최저가 · 결과를 큰 한 줄로 */}
            {pc && d.rounds.length > 0 && (
              <p className="q-answer d-block mt-4 mb-0">
                {[
                  d.rounds[d.rounds.length - 1]?.sale_date,
                  won(d.rounds[d.rounds.length - 1]?.min_price_krw ?? null),
                  d.rounds[d.rounds.length - 1]?.result,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
            <table className="pro-table mt-8">
              <thead>
                <tr>
                  <th>{t.pc.date}</th>
                  <th className="num">{t.pc.min}</th>
                  <th>{t.pc.result}</th>
                </tr>
              </thead>
              <tbody>
                {d.rounds.map((r) => (
                  <Fragment key={r.sale_date}>
                    <tr>
                      <td className="num">{r.sale_date}</td>
                      <td className="num">{won(r.min_price_krw)}</td>
                      <td>
                        {pc ? (
                          <span className={`chip ${ROUND_CHIP[r.result] ?? "gray"}`}>
                            {r.result}
                          </span>
                        ) : (
                          r.result
                        )}
                      </td>
                    </tr>
                    {/* 최저가가 다시 올라간 회차의 까닭(11/24 — 57221 10/19) */}
                    {r.note && (
                      <tr>
                        <td colSpan={3} className="fs-xs c-amber round-note">
                          ◆ {r.note}
                          {r.note_doc && (
                            <button onClick={() => openDoc(r.note_doc!)} className="link in ml-6">
                              {t.doc.open}
                            </button>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {!closed && <OddsLine odds={d.next_round.fail_odds} />}
          </section>
          <p className="sub fs-xs">{t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}</p>
          {/* 잘못된 정보 알리기(11/26 대표님) — 고치면 1,000P */}
          <ReportBox id={id} section="상세" />
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

const ROUND_CHIP: Record<string, string> = { 예정: "blue", 유찰: "gray", 매각: "green" };
// 「바로 꺼내 보기」 칸 → 그 칸이 든 질문(휴대폰은 질문이 접혀 있어 먼저 펼침)
const JUMP_Q: Record<string, string> = {
  station: "buy",
  building: "buy",
  tenant: "hold",
  fail: "hold",
  calc: "cost",
  "q-check": "check",
};

// 판정 한 줄(11/22 디자인): 「신호 — 설명 · 확인할 것 N가지」면 앞 신호를 ◆ 주황(빨강)으로
function Verdict({ text, tone }: { text: string; tone?: string }) {
  const i = text.lastIndexOf(" · ");
  // 휴대폰(11/23 M-Detail): 판정 한 줄을 색 판에 — 빨강 · 주황 · 그 밖은 초록
  const box = tone === "red" ? "v-red" : tone === "orange" ? "v-orange" : "v-green";
  if ((tone !== "orange" && tone !== "red") || i < 0)
    return <p className={`item-verdict ${box}`}>{text}</p>;
  return (
    <p className={`item-verdict ${box}`}>
      <span className={tone === "red" ? "c-red" : "c-orange"}>◆ {text.slice(0, i)}</span>
      {text.slice(i)}
    </p>
  );
}
