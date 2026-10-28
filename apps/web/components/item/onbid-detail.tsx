"use client";

import { useState } from "react";
import Link from "next/link";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import { Row } from "@/components/calc-box";
import type { OnbidDetail, Question } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { useIsPc } from "@/lib/use-pc";
import { DOT } from "@/components/item/shared";
import { SameHouse } from "@/components/item/same-house";
import { BuildingRows } from "@/components/item/building";

// 공매 상세(설계서 4절, 스토리보드 GM-ITEM-01·04·06). 경매와 같은 틀 — 결론 먼저, 다섯 질문은 눌러서.
const t = copy.onbid;
const WD = ["일", "월", "화", "수", "목", "금", "토"];

function when(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "";
  const d = new Date(iso);
  const k = new Date(d.getTime() + 9 * 3600_000); // 한국 시각
  const md = `${k.getUTCMonth() + 1}/${k.getUTCDate()}(${WD[k.getUTCDay()]})`;
  return withTime ? `${md} ${String(k.getUTCHours()).padStart(2, "0")}:00` : md;
}

const STATE_CHIP: Record<string, string> = {
  "확인 완료": "green",
  미확인: "gray",
  "공매엔 없어요": "gray",
  "전문가 확인 필요": "orange",
  "해당 없음": "gray",
};

function Rounds({ d }: { d: OnbidDetail }) {
  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{t.rounds}</div>
      {d.rounds.length === 0 && <p className="sub">{t.noRounds}</p>}
      {d.rounds.map((r, i) => (
        <div
          key={i}
          className="line-row"
          style={{
            fontSize: 14,
            color: r.label === "지난" ? "var(--muted)" : "inherit",
            background: r.label === "이번" ? "var(--blue-soft)" : undefined,
            borderRadius: 8,
            padding: "8px 6px",
          }}
        >
          <span>
            <b style={{ color: r.label === "이번" ? "var(--blue)" : "inherit" }}>{r.label}</b>{" "}
            {r.label === "지난"
              ? `개찰 ${when(r.open_at, false)} · ${r.result ?? ""}`
              : r.bid_end
                ? `${when(r.bid_start, false)} ~ ${when(r.bid_end, false)}`
                : copy.card.undecided}
          </span>
          <span>
            <b style={{ textDecoration: r.label === "지난" ? "line-through" : undefined }}>
              {won(r.min_price_krw)}
            </b>{" "}
            <span className="sub">{r.rate != null ? `${r.rate}%` : ""}</span>
          </span>
        </div>
      ))}
      {d.wait_line && (
        <div
          style={{
            marginTop: 8,
            padding: "10px 12px",
            borderRadius: 10,
            background: "var(--orange-soft)",
            color: "var(--orange)",
            fontSize: 14,
          }}
        >
          {d.wait_line}
        </div>
      )}
      <p className="sub" style={{ fontSize: 12, marginTop: 6 }}>
        {t.roundsNote}
      </p>
    </div>
  );
}

function Worth({ d }: { d: OnbidDetail }) {
  const m = d.market;
  const mn = d.min_price_krw ?? 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Rounds d={d} />
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{t.marketTitle}</div>
        {m ? (
          <>
            <div style={{ fontSize: 15, fontWeight: 600 }}>
              {m.price_krw > mn ? t.marketLine(won(m.price_krw - mn)) : t.marketAbove}
            </div>
            <div className="sub" style={{ fontSize: 13 }}>
              {won(m.price_krw)} · {t.marketBand(won(m.lo_krw), won(m.hi_krw), m.n)}
            </div>
            {d.appraisal_vs_market != null && d.appraisal_vs_market > 110 && (
              <div className="note blue" style={{ marginTop: 8, fontSize: 13 }}>
                {t.appraisalHigh(d.appraisal_vs_market)}
              </div>
            )}
          </>
        ) : (
          <p className="sub">{t.marketNone}</p>
        )}
      </div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 700 }}>{t.expectTitle}</div>
        <div className="sub" style={{ fontSize: 12 }}>
          {t.expectSub}
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr auto auto",
            columnGap: 12,
            rowGap: 6,
            fontSize: 14,
            marginTop: 8,
          }}
        >
          {t.expectCols.map((h) => (
            <span key={h} className="sub" style={{ fontSize: 12, margin: 0, textAlign: "right" }}>
              {h}
            </span>
          ))}
          {d.expected.map((e) => (
            <ExpectRow key={e.bucket} e={e} />
          ))}
        </div>
        <p className="sub" style={{ fontSize: 12, marginTop: 6 }}>
          {d.expected_basis}
        </p>
      </div>
    </div>
  );
}

function ExpectRow({ e }: { e: OnbidDetail["expected"][number] }) {
  const few = e.p50 == null;
  return (
    <>
      <span style={{ fontWeight: 600, color: few ? "var(--muted)" : undefined }}>
        {e.bucket} <span className="sub">({e.share ?? "-"}%)</span>
      </span>
      <span style={{ textAlign: "right" }}>{few ? "—" : `${e.p50}%`}</span>
      <span
        style={{ textAlign: "right", fontWeight: 700, color: few ? "var(--muted)" : undefined }}
      >
        {few ? `${t.fewSample} (${e.n}건)` : won(e.price_krw)}
      </span>
    </>
  );
}

function Body({ k, d }: { k: Question["key"]; d: OnbidDetail }) {
  if (k === "buy")
    return (
      <div>
        <Row label={t.address} value={d.address ?? d.title ?? "-"} />
        {d.area_m2 && <Row label={t.area} value={`${Math.round(d.area_m2 * 100) / 100}㎡`} />}
        {d.notice.name && <Row label={t.notice} value={d.notice.name} />}
        {d.notice.org && <Row label={t.org} value={d.notice.org} />}
        {d.building && <BuildingRows g={d.building} />}
      </div>
    );
  if (k === "hold")
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {d.warnings.map((w) => (
          <div key={w} style={{ fontSize: 14 }}>
            ◆ {w}
          </div>
        ))}
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{t.missingTitle}</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {d.missing_docs.map((x) => (
              <span key={x} className="chip gray">
                {x}
              </span>
            ))}
          </div>
          <p className="sub" style={{ fontSize: 13, marginTop: 8 }}>
            {t.missingWhy}
          </p>
        </div>
      </div>
    );
  if (k === "worth") return <Worth d={d} />;
  if (k === "cost")
    return (
      <div>
        <Row label={t.deposit} value={<b>{won(d.deposit_krw)}</b>} />
        <Row label={t.balance} value={t.balanceValue} />
        <Row label={t.moveOut} value={t.moveOutValue} />
      </div>
    );
  return (
    <div>
      {d.checklist.map((x) => (
        <div key={x.key} style={{ padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>{x.label}</span>
            <span className={`chip ${STATE_CHIP[x.state] ?? "gray"}`}>{x.state}</span>
          </div>
          <div className="sub" style={{ fontSize: 12, margin: 0 }}>
            {x.what}
          </div>
        </div>
      ))}
    </div>
  );
}

export function OnbidItem({ d }: { d: OnbidDetail }) {
  const [open, setOpen] = useState<Question["key"] | null>(null);
  const [copied, setCopied] = useState(false);
  const pc = useIsPc();
  const urgent = d.d_day != null && d.d_day <= 3;
  const solo = d.expected.find((e) => e.bucket === "혼자");
  const qs: { key: Question["key"]; answer: string; tone: Question["tone"] }[] = [
    { key: "buy", answer: [d.kind_name, d.usage].filter(Boolean).join(" · "), tone: "gray" },
    { key: "hold", answer: t.holdAnswer, tone: d.kind === "trust" ? "orange" : "red" },
    {
      key: "worth",
      answer: t.worthAnswer(
        d.market ? won(d.market.price_krw) : null,
        solo?.price_krw ? won(solo.price_krw) : null,
      ),
      tone: d.market || solo?.price_krw ? "blue" : "gray",
    },
    { key: "cost", answer: t.costAnswer(won(d.deposit_krw)), tone: "gray" },
    { key: "check", answer: t.checkAnswer(d.check_left), tone: "orange" },
  ];
  const copyNo = () => {
    navigator.clipboard?.writeText(d.case_no).then(
      () => setCopied(true),
      () => setCopied(false),
    );
  };
  const head = (
    <>
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      <section className="section">
        <div
          className="sub"
          style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}
        >
          <b style={{ color: urgent ? "var(--red)" : "var(--amber)" }}>
            {d.bid_end ? `${dday(d.d_day)} ${copy.card.closes} · ${when(d.bid_end)}` : t.undecided}
          </b>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              padding: "1px 6px",
              borderRadius: 5,
              border: "1px solid var(--text)",
            }}
          >
            {t.badge(d.kind_name ?? "")}
          </span>
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4 }}>
          {d.place} {d.usage ?? ""}
        </div>
        <div className="sub" style={{ fontSize: 13, margin: 0 }}>
          {d.case_no}
        </div>
        <div style={{ fontSize: 30, fontWeight: 700, marginTop: 6 }}>
          {won(d.min_price_krw)}{" "}
          <span style={{ fontSize: 14, fontWeight: 500, color: "var(--muted)" }}>
            {d.min_rate != null ? `${copy.card.ofAppraisal} ${d.min_rate}%` : ""}
            {d.failed_count ? ` · ${copy.card.failed(d.failed_count)}` : ""}
          </span>
        </div>
        {d.bid_end && (
          <div className="sub" style={{ fontSize: 13, margin: "4px 0 0" }}>
            {t.period(when(d.bid_start), when(d.bid_end))}
            {d.open_at ? ` · ${t.opens(when(d.open_at, false))}` : ""}
          </div>
        )}
        <p style={{ fontSize: 16, lineHeight: 1.5, margin: "12px 0 0" }}>{d.verdict}</p>
        <SameHouse list={d.same_house} />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          <span className="chip gray">● {t.checkAnswer(d.check_left)}</span>
          {d.market_rate != null && (
            <span className="chip blue">◆ {t.ofMarket(d.market_rate)}</span>
          )}
        </div>
      </section>
    </>
  );
  const actions = (
    <>
      <section className="section" style={{ display: "flex", gap: 8 }}>
        <button className="btn" onClick={copyNo} style={{ flex: 1 }}>
          {copied ? t.copied : t.copyNo}
        </button>
        <Link
          className="btn"
          href={`/item/${encodeURIComponent(d.item_id)}/report`}
          style={{ flex: 1 }}
        >
          {copy.report.open}
        </Link>
        {d.bid_end && (d.d_day ?? -1) >= 0 && (
          <Link
            className="btn primary"
            href={`/item/${encodeURIComponent(d.item_id)}/onbid-bid`}
            style={{ flex: 1 }}
          >
            {copy.onbidBid.title}
          </Link>
        )}
      </section>
      <a
        className="sub"
        href={t.onbidUrl}
        target="_blank"
        rel="noreferrer"
        style={{ display: "block", textAlign: "center", fontSize: 13, padding: "4px 0 12px" }}
      >
        {t.openOnbid}
      </a>
      <p className="sub" style={{ padding: "0 18px 24px", fontSize: 12 }}>
        {t.footer(d.computed_at.slice(0, 10))}
      </p>
    </>
  );
  // PC: 세 칸 — 왼쪽 요약·버튼(따라 내려옴) · 가운데 무엇을 사나·떠안는 것·확인할 것 · 오른쪽 얼마짜리·얼마가 드나
  if (pc) {
    const sec = (k: Question["key"]) => {
      const q = qs.find((x) => x.key === k) ?? qs[0]!;
      return (
        <section key={k} className="section">
          <div className="sub" style={{ margin: 0, fontSize: 13 }}>
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: 4,
                background: DOT[q.tone],
                marginRight: 6,
              }}
            />
            {t.q[k]}
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, margin: "2px 0 10px" }}>{q.answer}</div>
          <Body k={k} d={d} />
        </section>
      );
    };
    return (
      <main className="page">
        <PageHeader title="" back="history" right={<HeartButton id={d.item_id} />} />
        <div className="pc-grid g-26-44-30">
          <div className="pc-sticky">
            {head}
            {actions}
          </div>
          <div>{(["buy", "hold", "check"] as const).map(sec)}</div>
          <div>{(["worth", "cost"] as const).map(sec)}</div>
        </div>
      </main>
    );
  }
  return (
    <main className="page">
      <PageHeader title="" back="history" right={<HeartButton id={d.item_id} />} />
      {head}
      <section className="section" style={{ paddingTop: 0, paddingBottom: 0 }}>
        {qs.map((q) => (
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
                  {t.q[q.key]}
                </span>
                <span style={{ fontSize: 15, fontWeight: 600 }}>{q.answer}</span>
              </span>
              <span aria-hidden="true" style={{ color: "var(--faint)" }}>
                {open === q.key ? "⌃" : "›"}
              </span>
            </button>
            {open === q.key && (
              <div style={{ padding: "0 0 14px 18px" }}>
                <Body k={q.key} d={d} />
              </div>
            )}
          </div>
        ))}
      </section>

      {actions}
    </main>
  );
}
