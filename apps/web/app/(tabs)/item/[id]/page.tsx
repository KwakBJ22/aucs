"use client";

import { useEffect, useState } from "react";
import { Row } from "@/components/calc-box";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { SkDetail } from "@/components/skeleton";
import { isNotFound } from "@/lib/api/client";
import {
  requestDocs,
  fetchItem,
  isOnbid,
  type DocKind,
  type ItemDetail,
  type OnbidDetail,
} from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { rememberItem } from "@/lib/recent";
import { track } from "@/lib/track";
import { useIsPc } from "@/lib/use-pc";
import Link from "next/link";
import { useParams } from "next/navigation";
import { WsLink } from "@/components/item/actions";
import { Body } from "@/components/item/body";
import { answerOf } from "@/components/item/checklist";
import { DocSheet } from "@/components/item/doc-sheet";
import { OnbidItem } from "@/components/item/onbid-detail";
import { SameHouse } from "@/components/item/same-house";
import { ItemPhotos } from "@/components/item/item-photos";
import { OutcomeBand } from "@/components/item/outcome-band";
import { InterestLine } from "@/components/item/interest-line";
import { ItemPc } from "@/components/item/item-pc";
import { RegCtx, useMyRegistry } from "@/components/item/registry";
import { t, DOT, DocCtx } from "@/components/item/shared";

export default function Item() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<ItemDetail | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);
  const reg = useMyRegistry(decodeURIComponent(id));
  const [doc, setDoc] = useState<DocKind | null>(null);
  const pc = useIsPc();

  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);
  useEffect(() => {
    setFailed(false);
    fetchItem(decodeURIComponent(id))
      .then((x) => {
        setD(x);
        track("item_view", x.item_id);
        // 현황조사가 아직 없으면 서류 받기를 줄 세움(11/4) — 손님이 본 물건부터 「자료 기다림」이 채워짐
        if (!isOnbid(x) && !x.tags?.find((g) => g.label === "현황조사")?.ok) requestDocs(x.item_id);
        rememberItem(
          x.item_id,
          `${isOnbid(x) ? "공매" : x.court} ${x.case_no} · ${x.place} ${x.building ?? x.usage ?? ""}`,
        );
      })
      .catch((e: unknown) => (isNotFound(e) ? setD(null) : setFailed(true)));
  }, [id, tries]);

  if (failed && d === undefined)
    return (
      <main className="page">
        <PageHeader title="" back="history" />
        <LoadError onRetry={() => setTries((n) => n + 1)} />
      </main>
    );
  if (d === undefined)
    return (
      <main className="page">
        <div className="topbar" />
        <SkDetail />
      </main>
    );
  if (d === null)
    return (
      <main className="page">
        <p className="sub p-24">{t.notFound}</p>
      </main>
    );
  if (isOnbid(d)) return <OnbidItem d={d as unknown as OnbidDetail} />; // 공매(10/28)
  const urgent = d.d_day != null && d.d_day <= 7;
  if (pc)
    return (
      <RegCtx.Provider value={reg}>
        <DocCtx.Provider value={setDoc}>
          <ItemPc d={d} reg={reg} />
          {doc && <DocSheet id={d.item_id} kind={doc} onClose={() => setDoc(null)} />}
        </DocCtx.Provider>
      </RegCtx.Provider>
    );
  return (
    <RegCtx.Provider value={reg}>
      <DocCtx.Provider value={setDoc}>
        <main className="page">
          <PageHeader
            title=""
            back="history"
            right={
              <div className="d-flex ai-center gap-8">
                <WsLink id={d.item_id} />
                <HeartButton id={d.item_id} />
              </div>
            }
          />
          {d.fatal && <div className="fatal">{d.fatal}</div>}
          {d.d_day != null && d.d_day <= 1 && d.d_day >= 0 && (
            <Link
              href={`/item/${encodeURIComponent(d.item_id)}/bid-day`}
              className="chip orange mh-36 mt-8 d-inline-flex"
            >
              {copy.bidDay.title} ›
            </Link>
          )}
          <section className="section">
            <div className="sub">
              <b
                style={{
                  color:
                    (d.d_day ?? 0) < 0 ? "var(--muted)" : urgent ? "var(--red)" : "var(--amber)",
                }}
              >
                {dday(d.d_day)}
              </b>{" "}
              · {d.sale_date} · {d.court} {d.case_no}
            </div>
            <h1 className="fs-base fw-6 mt-4 mb-0">
              {d.place} {d.building ?? d.usage}
            </h1>
            <div className="fs-3xl fw-7 mt-6">
              {won(d.min_price_krw)}{" "}
              <span className="fs-md fw-5 c-muted d-inline-block">
                {copy.card.ofAppraisal} {d.min_rate}%
                {d.failed_count ? ` · ${copy.card.failed(d.failed_count)}` : ""}
              </span>
            </div>
            <OutcomeBand d={d} />
            <p className="fs-base lh-15 mt-12 mb-0 mx-0">{d.verdict}</p>
            <InterestLine v={d.interest} />
            <SameHouse list={d.same_house} />
            <ItemPhotos list={d.photos} />
          </section>

          <section className="section pt-0 pb-0">
            {d.questions.map((q) => (
              <div key={q.key} style={{}}>
                <button
                  onClick={() => setOpen(open === q.key ? null : q.key)}
                  className="w-full b-0 bg-none ta-left py-14 px-0 mh-44 d-flex gap-10 ai-start c-inherit"
                >
                  <span
                    className="r-4 mt-6 f-none"
                    style={{ width: 8, height: 8, background: DOT[q.tone] }}
                  />
                  <span className="f-1">
                    <span className="sub d-block m-0 fs-sm">{q.title}</span>
                    <span className="fs-base fw-6">{answerOf(q, reg.u)}</span>
                  </span>
                  <span aria-hidden="true" className="c-faint">
                    {open === q.key ? "⌃" : "›"}
                  </span>
                </button>
                {open === q.key && (
                  <div className="pt-0 pb-14 pl-18 pr-0">
                    <Body q={q} d={d} />
                  </div>
                )}
              </div>
            ))}
          </section>

          <section className="section">
            {d.next_round.min_price_krw && !d.outcome?.closed && (
              <Row
                label={t.nextRound}
                value={
                  <b>
                    {won(d.next_round.min_price_krw)}
                    {d.next_round.verified ? "" : ` ${t.nextRoundGuess}`}
                  </b>
                }
              />
            )}
            {d.next_round.fail_odds && !d.outcome?.closed && (
              <div className="sub fs-xs mt-2">
                {t.failOdds(d.next_round.fail_odds.of10, d.next_round.fail_odds.n)}
              </div>
            )}
            {d.rounds.length > 0 && <div className="fs-md fw-6 mt-10 mb-2 mx-0">{t.rounds}</div>}
            {d.rounds.map((r) => (
              <Row
                key={r.sale_date}
                label={r.sale_date}
                value={`${won(r.min_price_krw)} · ${r.result}`}
              />
            ))}
          </section>
          <p className="sub pt-0 pb-24 px-18 fs-xs">
            {t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}
          </p>
          {/* 주 버튼 하나, 화면 아래에 붙임(08-look 5절) — 입찰가 계산·모의입찰로 감 */}
          {(d.d_day ?? -1) >= 0 && (
            <div className="cta-bar">
              <Link href={`/item/${encodeURIComponent(d.item_id)}/calc`} className="btn primary">
                {t.bidTry}
              </Link>
            </div>
          )}
          {doc && <DocSheet id={d.item_id} kind={doc} onClose={() => setDoc(null)} />}
        </main>
      </DocCtx.Provider>
    </RegCtx.Provider>
  );
}
