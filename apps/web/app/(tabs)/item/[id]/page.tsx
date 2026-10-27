"use client";

import { useEffect, useState } from "react";
import { Row } from "@/components/calc-box";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { isNotFound } from "@/lib/api/client";
import { fetchItem, type DocKind, type ItemDetail } from "@/lib/api/items";
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
        rememberItem(
          x.item_id,
          `${x.court} ${x.case_no} · ${x.place} ${x.building ?? x.usage ?? ""}`,
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
      <main className="page" aria-busy="true">
        <div className="topbar" />
        {[120, 260].map((h) => (
          <section key={h} className="section" style={{ height: h, opacity: 0.5 }} />
        ))}
      </main>
    );
  if (d === null)
    return (
      <main className="page">
        <p className="sub" style={{ padding: 24 }}>
          {t.notFound}
        </p>
      </main>
    );
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
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <WsLink id={d.item_id} />
                <HeartButton id={d.item_id} />
              </div>
            }
          />
          {d.fatal && <div className="fatal">{d.fatal}</div>}
          {d.d_day != null && d.d_day <= 1 && d.d_day >= 0 && (
            <Link
              href={`/item/${encodeURIComponent(d.item_id)}/bid-day`}
              className="chip orange"
              style={{ minHeight: 36, marginTop: 8, display: "inline-flex" }}
            >
              {copy.bidDay.title} ›
            </Link>
          )}
          <section className="section">
            <div className="sub">
              <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>{dday(d.d_day)}</b> ·{" "}
              {d.sale_date} · {d.court} {d.case_no}
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4 }}>
              {d.place} {d.building ?? d.usage}
            </div>
            <div style={{ fontSize: 30, fontWeight: 700, marginTop: 6 }}>
              {won(d.min_price_krw)}{" "}
              <span style={{ fontSize: 14, fontWeight: 500, color: "var(--muted)" }}>
                {copy.card.ofAppraisal} {d.min_rate}%
                {d.failed_count ? ` · ${copy.card.failed(d.failed_count)}` : ""}
              </span>
            </div>
            <p style={{ fontSize: 16, lineHeight: 1.5, margin: "12px 0 0" }}>{d.verdict}</p>
          </section>

          <section className="section" style={{ paddingTop: 0, paddingBottom: 0 }}>
            {d.questions.map((q) => (
              <div key={q.key} style={{ borderBottom: "1px solid var(--line)" }}>
                <button
                  onClick={() => setOpen(open === q.key ? null : q.key)}
                  style={{
                    width: "100%",
                    border: 0,
                    background: "none",
                    textAlign: "left",
                    padding: "14px 0",
                    minHeight: 44,
                    display: "flex",
                    gap: 10,
                    alignItems: "flex-start",
                    color: "inherit",
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: DOT[q.tone],
                      marginTop: 7,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ flexGrow: 1 }}>
                    <span className="sub" style={{ display: "block", margin: 0, fontSize: 13 }}>
                      {q.title}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 600 }}>{answerOf(q, reg.u)}</span>
                  </span>
                  <span aria-hidden="true" style={{ color: "var(--faint)" }}>
                    {open === q.key ? "⌃" : "›"}
                  </span>
                </button>
                {open === q.key && (
                  <div style={{ padding: "0 0 14px 18px" }}>
                    <Body q={q} d={d} />
                  </div>
                )}
              </div>
            ))}
          </section>

          <section className="section">
            {d.next_round.min_price_krw && (
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
            {d.rounds.length > 0 && (
              <div style={{ fontSize: 14, fontWeight: 600, margin: "10px 0 2px" }}>{t.rounds}</div>
            )}
            {d.rounds.map((r) => (
              <Row
                key={r.sale_date}
                label={r.sale_date}
                value={`${won(r.min_price_krw)} · ${r.result}`}
              />
            ))}
          </section>
          <p className="sub" style={{ padding: "0 18px 24px", fontSize: 12 }}>
            {t.footer(d.computed_at ? d.computed_at.slice(0, 10) : "-")}
          </p>
          {doc && <DocSheet id={d.item_id} kind={doc} onClose={() => setDoc(null)} />}
        </main>
      </DocCtx.Provider>
    </RegCtx.Provider>
  );
}
