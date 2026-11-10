"use client";

import { copyText } from "@/lib/copy-text";
import { useState } from "react";
import Link from "next/link";
import { HeartButton } from "@/components/heart-button";
import { PageHeader } from "@/components/layout/page-header";
import { Row } from "@/components/calc-box";
import type { OnbidDetail, Question } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, parseTime, won } from "@/lib/format";
import { DDay } from "@/components/dday";
import { useIsPc } from "@/lib/use-pc";
import { DOT } from "@/components/item/shared";
import { SameHouse } from "@/components/item/same-house";
import { InterestLine } from "@/components/item/interest-line";
import { BuildingRows } from "@/components/item/building";

// 공매 상세(설계서 4절, 스토리보드 GM-ITEM-01·04·06). 경매와 같은 틀 — 결론 먼저, 다섯 질문은 눌러서.
const t = copy.onbid;
const WD = ["일", "월", "화", "수", "목", "금", "토"];

function when(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "";
  const d = parseTime(iso);
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
      <div className="fs-md fw-7 mb-4">{t.rounds}</div>
      {d.rounds.length === 0 && <p className="sub">{t.noRounds}</p>}
      {d.rounds.map((r, i) => (
        <div
          key={i}
          className="line-row fs-md r-8 py-8 px-6"
          style={{
            color: r.label === "지난" ? "var(--muted)" : "inherit",
            background: r.label === "이번" ? "var(--blue-soft)" : undefined,
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
        <div className="mt-8 py-10 px-12 r-10 bg-orange-soft c-orange fs-md">{d.wait_line}</div>
      )}
      <p className="sub fs-xs mt-6">{t.roundsNote}</p>
    </div>
  );
}

function Worth({ d }: { d: OnbidDetail }) {
  const m = d.market;
  const mn = d.min_price_krw ?? 0;
  return (
    <div className="d-flex f-col gap-14">
      <Rounds d={d} />
      <div>
        <div className="fs-md fw-7 mb-4">{t.marketTitle}</div>
        {m ? (
          <>
            <div className="fs-base fw-6">
              {m.price_krw > mn ? t.marketLine(won(m.price_krw - mn)) : t.marketAbove}
            </div>
            <div className="sub fs-sm">
              {won(m.price_krw)} · {t.marketBand(won(m.lo_krw), won(m.hi_krw), m.n)}
            </div>
            {d.appraisal_vs_market != null && d.appraisal_vs_market > 110 && (
              <div className="note blue mt-8 fs-sm">{t.appraisalHigh(d.appraisal_vs_market)}</div>
            )}
          </>
        ) : (
          <p className="sub">{t.marketNone}</p>
        )}
      </div>
      <div>
        <div className="fs-md fw-7">{t.expectTitle}</div>
        <div className="sub fs-xs">{t.expectSub}</div>
        <div
          className="d-grid fs-md mt-8"
          style={{ gridTemplateColumns: "1fr auto auto", columnGap: 12, rowGap: 6 }}
        >
          {t.expectCols.map((h) => (
            <span key={h} className="sub fs-xs m-0 ta-right">
              {h}
            </span>
          ))}
          {d.expected.map((e) => (
            <ExpectRow key={e.bucket} e={e} />
          ))}
        </div>
        <p className="sub fs-xs mt-6">{d.expected_basis}</p>
      </div>
    </div>
  );
}

function ExpectRow({ e }: { e: OnbidDetail["expected"][number] }) {
  const few = e.p50 == null;
  return (
    <>
      <span className="fw-6" style={{ color: few ? "var(--muted)" : undefined }}>
        {e.bucket} <span className="sub">({e.share ?? "-"}%)</span>
      </span>
      <span className="ta-right">{few ? "—" : `${e.p50}%`}</span>
      <span className="ta-right fw-7" style={{ color: few ? "var(--muted)" : undefined }}>
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
        <Link href={`/item/${encodeURIComponent(d.item_id)}/notice`} className="link">
          {copy.onbidNotice.link}
        </Link>
        {d.building && <BuildingRows g={d.building} />}
      </div>
    );
  if (k === "hold")
    return (
      <div className="d-flex f-col gap-10">
        {d.warnings.map((w) => (
          <div key={w} className="fs-md">
            ◆ {w}
          </div>
        ))}
        <div>
          <div className="fs-md fw-7 mb-6">{t.missingTitle}</div>
          <div className="d-flex gap-6 f-wrap">
            {d.missing_docs.map((x) => (
              <span key={x} className="chip gray">
                {x}
              </span>
            ))}
          </div>
          <p className="sub fs-sm mt-8">{t.missingWhy}</p>
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
        <div key={x.key} className="py-10 px-0">
          <div className="d-flex jc-between gap-8">
            <span className="fs-base fw-6">{x.label}</span>
            <span className={`chip ${STATE_CHIP[x.state] ?? "gray"}`}>{x.state}</span>
          </div>
          <div className="sub fs-xs m-0">{x.what}</div>
        </div>
      ))}
    </div>
  );
}

export function OnbidItem({ d }: { d: OnbidDetail }) {
  const [open, setOpen] = useState<Question["key"] | null>(null);
  const [copied, setCopied] = useState(false);
  const pc = useIsPc();
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
    void copyText(d.case_no).then(
      () => setCopied(true),
      () => setCopied(false),
    );
  };
  const head = (
    <>
      {d.fatal && <div className="fatal">{d.fatal}</div>}
      <section className="section">
        <div className="sub d-flex gap-8 f-wrap ai-center">
          <DDay d={d.d_day}>
            {d.bid_end ? `${dday(d.d_day)} ${copy.card.closes} · ${when(d.bid_end)}` : t.undecided}
          </DDay>
          <span className="chip gray">{t.badge(d.kind_name ?? "")}</span>
        </div>
        <h1 className="fs-base fw-6 mt-4 mb-0">
          {d.place} {d.usage ?? ""}
        </h1>
        <div className="sub fs-sm m-0">{d.case_no}</div>
        <div className="fs-3xl fw-7 mt-6">
          {won(d.min_price_krw)}{" "}
          <span className="fs-md fw-5 c-muted">
            {d.min_rate != null ? `${copy.card.ofAppraisal} ${d.min_rate}%` : ""}
            {d.failed_count ? ` · ${copy.card.failed(d.failed_count)}` : ""}
          </span>
        </div>
        {d.bid_end && (
          <div className="sub fs-sm mt-4 mb-0 mx-0">
            {t.period(when(d.bid_start), when(d.bid_end))}
            {d.open_at ? ` · ${t.opens(when(d.open_at, false))}` : ""}
          </div>
        )}
        <p className="fs-base lh-15 mt-12 mb-0 mx-0">{d.verdict}</p>
        <InterestLine v={d.interest} />
        <SameHouse list={d.same_house} />
        <div className="d-flex gap-6 f-wrap mt-8">
          <span className="chip gray">● {t.checkAnswer(d.check_left)}</span>
          {d.market_rate != null && (
            <span className="chip blue">◆ {t.ofMarket(d.market_rate)}</span>
          )}
        </div>
      </section>
    </>
  );
  const live = Boolean(d.bid_end && (d.d_day ?? -1) >= 0);
  // 주 버튼 하나(폭 가득) + 덜 중요한 일은 아래 글자 링크(08-look 5절)
  const actions = (
    <>
      <section className="section">
        {live && (
          <Link className="btn primary" href={`/item/${encodeURIComponent(d.item_id)}/onbid-bid`}>
            {copy.onbidBid.title}
          </Link>
        )}
        <div className={`d-flex jc-center ai-center gap-16 f-wrap${live ? " mt-14" : ""}`}>
          <button onClick={copyNo} className="btn secondary sm">
            {copied ? t.copied : t.copyNo}
          </button>
          <Link href={`/item/${encodeURIComponent(d.item_id)}/report`} className="link">
            {copy.report.open}
          </Link>
          <a href={t.onbidUrl} target="_blank" rel="noreferrer" className="link">
            {t.openOnbid}
          </a>
        </div>
      </section>
      <p className="sub pt-0 pb-24 px-18 fs-xs">{t.footer(d.computed_at.slice(0, 10))}</p>
    </>
  );
  // PC: 세 칸 — 왼쪽 요약·버튼(따라 내려옴) · 가운데 무엇을 사나·떠안는 것·확인할 것 · 오른쪽 얼마짜리·얼마가 드나
  if (pc) {
    const sec = (k: Question["key"]) => {
      const q = qs.find((x) => x.key === k) ?? qs[0]!;
      return (
        <section key={k} className="section">
          <div className="sub m-0 fs-sm">
            <span
              className="d-inline-block r-4 mr-6"
              style={{ width: 8, height: 8, background: DOT[q.tone] }}
            />
            {t.q[k]}
          </div>
          <div className="fs-base fw-7 mt-2 mb-10 mx-0">{q.answer}</div>
          <Body k={k} d={d} />
        </section>
      );
    };
    return (
      <main className="page">
        <div className="d-flex jc-end pt-12">
          <HeartButton id={d.item_id} />
        </div>
        <div className="pc-grid g-26-44-30">
          <div className="pc-sticky">
            {head}
            {actions}
          </div>
          <div className="kv-left">{(["buy", "hold", "check"] as const).map(sec)}</div>
          <div className="kv-left">{(["worth", "cost"] as const).map(sec)}</div>
        </div>
      </main>
    );
  }
  return (
    <main className="page">
      <PageHeader title="" back="history" right={<HeartButton id={d.item_id} />} />
      {head}
      <section className="section pt-0 pb-0">
        {qs.map((q) => (
          <div key={q.key} style={{}}>
            <button
              onClick={() => setOpen(open === q.key ? null : q.key)}
              aria-expanded={open === q.key}
              className="q-head fold py-14"
            >
              <span
                className="r-4 mt-6 f-none"
                style={{ width: 8, height: 8, background: DOT[q.tone] }}
              />
              <span className="f-1">
                <span className="sub d-block m-0 fs-sm">{t.q[q.key]}</span>
                <span className="fs-base fw-6">{q.answer}</span>
              </span>
            </button>
            {open === q.key && (
              <div className="pt-0 pb-14 pl-18 pr-0">
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
