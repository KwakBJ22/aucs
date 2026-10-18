"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { HeartButton } from "@/components/heart-button";
import {
  fetchBidCheck,
  fetchCalc,
  fetchItem,
  type BidCheck,
  type Calc,
  type ItemDetail,
  type Question,
} from "@/lib/api/items";
import { loadProfile, saveProfile } from "@/lib/profile";
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

function Row({ label, value }: { label: React.ReactNode; value: React.ReactNode }) {
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

// 입찰가 계산(CALC-01): 집 수 → 세 경우 → 슬라이더 → 필요한 현금. 금액은 한글로도 읽어 줍니다.
function CalcBox({ id }: { id: string }) {
  const c = t.calc;
  const prof = typeof window === "undefined" ? null : loadProfile();
  const [homes, setHomes] = useState<number | null>(prof?.homes ?? null);
  const [first, setFirst] = useState(Boolean(prof?.firstTime));
  const [bid, setBid] = useState<number | null>(null);
  const [loan, setLoan] = useState<number | null>(null);
  const [editLoan, setEditLoan] = useState(false);
  const [d, setD] = useState<Calc | null>(null);
  const [chk, setChk] = useState<BidCheck | null>(null);

  useEffect(() => {
    if (homes == null) return;
    const h = setTimeout(() => {
      fetchCalc(id, { bid, homes, first, loan })
        .then((r) => {
          setD(r);
          if (bid == null) setBid(r.selected.bid_krw);
        })
        .catch(() => setD(null));
      if (bid)
        fetchBidCheck(id, bid)
          .then(setChk)
          .catch(() => setChk(null));
    }, 250);
    return () => clearTimeout(h);
  }, [id, bid, homes, first, loan]);

  const pickHomes = (n: number) => {
    setHomes(n);
    const p = loadProfile() ?? { regions: [], cash: null, purpose: null };
    saveProfile({ ...p, homes: n, firstTime: n === 0 ? first : false });
  };
  const s = d?.selected;
  const over = d?.cap_krw != null && s != null && s.bid_krw > d.cap_krw;
  const myCash = prof?.cash ?? null;
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>{c.homesQ}</div>
      <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
        {c.homes.map((label, i) => (
          <button
            key={label}
            className={`chip ${homes === i ? "green" : "gray"}`}
            style={{ minHeight: 36, border: 0 }}
            onClick={() => pickHomes(i)}
          >
            {label}
          </button>
        ))}
        {homes === 0 && (
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
            <input type="checkbox" checked={first} onChange={(e) => setFirst(e.target.checked)} />
            {c.firstTime}
          </label>
        )}
      </div>
      {d && s && (
        <>
          {d.cases.length > 0 && (
            <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
              {d.cases.map((x) => (
                <button
                  key={x.key}
                  onClick={() => setBid(x.bid_krw)}
                  style={{
                    flex: 1,
                    padding: "8px 4px",
                    borderRadius: 8,
                    border: `1px solid ${s.bid_krw === x.bid_krw ? "var(--green)" : "var(--line)"}`,
                    background: "none",
                    color: "inherit",
                    fontSize: 12,
                  }}
                >
                  <b style={{ fontSize: 13 }}>{c.cases[x.key]}</b>
                  <div>{won(x.bid_krw)}</div>
                  <div className="sub" style={{ margin: 0 }}>
                    {c.chance(x.chance)}
                  </div>
                </button>
              ))}
            </div>
          )}
          <input
            type="range"
            min={d.slider.min}
            max={d.slider.max}
            step={d.slider.step}
            value={s.bid_krw}
            onChange={(e) => setBid(Number(e.target.value))}
            style={{ width: "100%", marginTop: 12 }}
            aria-label={t.bidTry}
          />
          <div style={{ fontSize: 22, fontWeight: 700 }}>{won(s.bid_krw)}</div>
          {chk && (
            <div style={{ fontSize: 13 }}>
              {chk.korean}
              {chk.level !== "ok" && (
                <div style={{ color: chk.level === "block" ? "var(--red)" : "var(--amber)" }}>
                  {chk.message}
                </div>
              )}
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <Row
              label={`${c.loan} · ${c.region[d.cls]} ${s.loan.pct}%`}
              value={
                <>
                  − {won(s.loan_krw)}{" "}
                  <button
                    onClick={() => setEditLoan(!editLoan)}
                    style={{ border: 0, background: "none", color: "var(--blue)", fontSize: 13 }}
                  >
                    {c.loanEdit}
                  </button>
                </>
              }
            />
            {editLoan && (
              <input
                inputMode="numeric"
                placeholder={c.loanPlaceholder}
                onChange={(e) => {
                  const n = Number(e.target.value.replace(/[^0-9]/g, ""));
                  setLoan(e.target.value ? n : null);
                }}
                style={{
                  width: "100%",
                  fontSize: 16,
                  padding: "8px 10px",
                  border: "1px solid var(--line)",
                  borderRadius: 8,
                }}
              />
            )}
            <div className="sub" style={{ margin: 0, fontSize: 12 }}>
              {s.loan.note ?? c.loanHint}
            </div>
            <Row label={c.tax(s.tax.total_pct)} value={`+ ${won(s.tax.tax_krw)}`} />
            <Row label={c.reg} value={`+ ${won(s.registration_krw)}`} />
            {s.assumed_krw > 0 && <Row label={c.assumed} value={`+ ${won(s.assumed_krw)}`} />}
            <Row
              label={<b>{c.cash}</b>}
              value={<b style={{ fontSize: 18 }}>{won(s.cash_krw)}</b>}
            />
            {myCash && (
              <div
                style={{
                  fontSize: 13,
                  textAlign: "right",
                  color: s.cash_krw > myCash ? "var(--amber)" : "var(--muted)",
                }}
              >
                {c.vsCash(s.cash_krw > myCash, won(Math.abs(s.cash_krw - myCash)))}
              </div>
            )}
            {d.cap_krw != null && (
              <div
                style={{
                  fontSize: 13,
                  marginTop: 6,
                  color: over ? "var(--red)" : "var(--muted)",
                }}
              >
                ◆ {c.cap(won(d.cap_krw))}
              </div>
            )}
            {d.resale && <div className="sub">{t.resale}</div>}
          </div>
        </>
      )}
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
        {d.failure_types.length > 0 && (
          <div className="sub" style={{ marginTop: 8 }}>
            {t.failureTypes}: {d.failure_types.map((x) => x.title).join(" · ")}
          </div>
        )}
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
        {b.market && (
          <>
            <Row label={t.market(b.market.n)} value={<b>{won(b.market.price_krw)}</b>} />
            <div className="sub" style={{ margin: 0, fontSize: 12 }}>
              {t.recentTrades}{" "}
              {b.market.recent
                .slice(0, 3)
                .map(
                  (x: { date: string; floor: number | null; price_krw: number }) =>
                    `${x.date.slice(2, 7).replace("-", ".")} ${x.floor ?? "-"}층 ${won(x.price_krw)}`,
                )
                .join(" · ")}
            </div>
          </>
        )}
        {b.notes.map((n: string) => (
          <div key={n} style={{ fontSize: 14, color: "var(--amber)", padding: "2px 0" }}>
            ◆ {n}
          </div>
        ))}
      </>
    ) : null;
  if (q.key === "cost")
    return (
      <>
        <Row label={t.deposit} value={<b>{won(b.deposit_krw)}</b>} />
        <p style={{ fontSize: 14, margin: "8px 0 4px" }}>{b.schedule_line}</p>
        <div className="sub" style={{ margin: "8px 0 2px" }}>
          {t.deadlines}
        </div>
        {b.deadlines.map((x: { key: string; label: string; short: string }) => (
          <Row key={x.key} label={x.label} value={x.short} />
        ))}
        <CalcBox id={d.item_id} />
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
