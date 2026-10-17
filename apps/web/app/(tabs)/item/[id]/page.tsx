"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { HeartButton } from "@/components/heart-button";
import { fetchItem, type ItemDetail, type Question } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

const t = copy.item;
const DOT: Record<Question["tone"], string> = {
  green: "var(--green)",
  gray: "var(--faint)",
  orange: "var(--amber)",
  red: "var(--red)",
  blue: "var(--blue)",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 12,
        padding: "6px 0",
        fontSize: 14,
      }}
    >
      <span className="sub" style={{ margin: 0 }}>
        {label}
      </span>
      <span style={{ textAlign: "right" }}>{value}</span>
    </div>
  );
}

function Body({ q, d }: { q: Question; d: ItemDetail }) {
  const b = q.body;
  if (q.key === "buy")
    return (
      <>
        <Row label="주소" value={b.address ?? "-"} />
        {b.area_m2 && (
          <Row
            label="면적"
            value={`${b.area_m2.toFixed(1)}㎡ (${Math.round(b.area_m2 / 3.3058)}평)`}
          />
        )}
        {b.is_share && <Row label="" value={<b style={{ color: "var(--red)" }}>{t.share}</b>} />}
        {b.note && (
          <p className="sub" style={{ whiteSpace: "pre-wrap" }}>
            {b.note}
          </p>
        )}
      </>
    );
  if (q.key === "hold")
    return (
      <>
        {b.tenants.length === 0 && <p className="sub">{t.tenantsNone}</p>}
        {b.tenants.map((x: Record<string, string | number | null>, i: number) => (
          <div
            key={i}
            style={{ padding: "6px 0", fontSize: 14, borderBottom: "1px solid var(--line)" }}
          >
            <b>{x.name ?? "임차인"}</b> {x.part ?? ""}
            <div className="sub" style={{ margin: 0 }}>
              {[
                x.move_in && `${t.moveIn} ${x.move_in}`,
                x.fixed && `${t.fixed} ${x.fixed}`,
                x.claim && `${t.claim} ${x.claim}`,
                x.deposit_krw && `보증금 ${won(Number(x.deposit_krw))}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
        ))}
        {b.signals
          .filter((s: { status: string }) => s.status !== "모름")
          .map((s: { rule_id: string; title: string; level: string }) => (
            <div
              key={s.rule_id}
              style={{
                fontSize: 14,
                padding: "6px 0",
                color: s.level === "fatal" ? "var(--red)" : "var(--amber)",
              }}
            >
              ◆ {s.title}
            </div>
          ))}
      </>
    );
  if (q.key === "worth")
    return b.range_krw ? (
      <>
        <Row
          label={t.rangeLabel}
          value={
            <b>
              {won(b.range_krw[0])} ~ {won(b.range_krw[1])}
            </b>
          }
        />
        <p className="sub">{t.sample(b.rate.n)}</p>
      </>
    ) : null;
  if (q.key === "cost")
    return (
      <>
        <Row label={t.deposit} value={<b>{won(b.deposit_krw)}</b>} />
        <p className="sub">{t.calcSoon}</p>
      </>
    );
  return (
    <>
      {b.unknown.map((s: { rule_id: string; title: string }) => (
        <div key={s.rule_id} style={{ fontSize: 14, padding: "6px 0" }}>
          ● {s.title}
        </div>
      ))}
      {b.claim_deadline && <Row label={t.claimDeadline} value={b.claim_deadline} />}
      {b.events.length > 0 && (
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 10 }}>{t.events}</div>
      )}
      {b.events.map(
        (
          e: { date: string; category: string; text: string; after_deadline: boolean },
          i: number,
        ) => (
          <div key={i} style={{ fontSize: 13, padding: "4px 0" }}>
            <span className="sub" style={{ margin: 0 }}>
              {e.date}
            </span>{" "}
            {e.category}
            {e.after_deadline && <b style={{ color: "var(--amber)" }}> · {t.afterDeadline}</b>}
          </div>
        ),
      )}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
        {d.tags.map((g) => (
          <span key={g.label} className={`chip ${g.ok ? "green" : "gray"}`}>
            {g.label}
            {g.ok ? "" : " 미확인"}
          </span>
        ))}
      </div>
    </>
  );
}

export default function Item() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [d, setD] = useState<ItemDetail | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    fetchItem(decodeURIComponent(id))
      .then(setD)
      .catch(() => setD(null));
  }, [id]);

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
  return (
    <main className="page">
      <div className="topbar">
        <button
          aria-label={t.back}
          onClick={() => router.back()}
          style={{
            border: 0,
            background: "none",
            fontSize: 20,
            minWidth: 44,
            minHeight: 44,
            textAlign: "left",
          }}
        >
          ←
        </button>
        <HeartButton id={d.item_id} />
      </div>
      {d.fatal && <div className="fatal">{d.fatal}</div>}
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
                <span style={{ fontSize: 15, fontWeight: 600 }}>{q.answer}</span>
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
    </main>
  );
}
