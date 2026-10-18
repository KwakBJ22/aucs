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
  const [selling, setSelling] = useState(Boolean(prof?.selling));
  const [dsrOpen, setDsrOpen] = useState(false);
  const [income, setIncome] = useState<number | null>(null);
  const [otherMonthly, setOtherMonthly] = useState<number | null>(null);
  const [bid, setBid] = useState<number | null>(null);
  const [loan, setLoan] = useState<number | null>(null);
  const [editLoan, setEditLoan] = useState(false);
  const [d, setD] = useState<Calc | null>(null);
  const [chk, setChk] = useState<BidCheck | null>(null);

  useEffect(() => {
    if (homes == null) return;
    const h = setTimeout(() => {
      fetchCalc(id, {
        bid,
        homes,
        first,
        loan,
        selling: homes === 1 && selling,
        income,
        otherMonthly,
      })
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
  }, [id, bid, homes, first, loan, selling, income, otherMonthly]);

  const pickHomes = (n: number) => {
    setHomes(n);
    const p = loadProfile() ?? { regions: [], cash: null, purpose: null };
    saveProfile({ ...p, homes: n, firstTime: n === 0 ? first : false });
  };
  const toggle = (k: "firstTime" | "selling", v: boolean) => {
    if (k === "firstTime") setFirst(v);
    else setSelling(v);
    const p = loadProfile() ?? { regions: [], cash: null, purpose: null };
    saveProfile({ ...p, [k]: v });
  };
  const manInput = (label: string, set: (n: number | null) => void) => (
    <label style={{ display: "block", fontSize: 13, marginTop: 6 }}>
      <span className="sub" style={{ margin: 0 }}>
        {label}
      </span>
      <input
        inputMode="numeric"
        onChange={(e) => {
          const n = Number(e.target.value.replace(/[^0-9]/g, ""));
          set(n ? n * 10_000 : null);
        }}
        style={{
          width: "100%",
          fontSize: 16,
          padding: "8px 10px",
          border: "1px solid var(--line)",
          borderRadius: 8,
        }}
      />
    </label>
  );
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
            <input
              type="checkbox"
              checked={first}
              onChange={(e) => toggle("firstTime", e.target.checked)}
            />
            {c.firstTime}
          </label>
        )}
        {homes === 1 && (
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
            <input
              type="checkbox"
              checked={selling}
              onChange={(e) => toggle("selling", e.target.checked)}
            />
            {c.selling}
          </label>
        )}
      </div>
      {homes === 1 && selling && (
        <div className="sub" style={{ margin: "4px 0 0", fontSize: 12 }}>
          {c.sellingHint}
        </div>
      )}
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
              {s.loan.by_dsr && s.dsr ? c.byDsr(s.dsr.rate_pct) : (s.loan.note ?? c.loanHint)}{" "}
              <button
                onClick={() => setDsrOpen(!dsrOpen)}
                style={{ border: 0, background: "none", color: "var(--blue)", fontSize: 12 }}
              >
                {c.dsrOpen}
              </button>
            </div>
            {dsrOpen && (
              <>
                {manInput(c.income, setIncome)}
                {manInput(c.otherMonthly, setOtherMonthly)}
              </>
            )}
            <Row
              label={
                s.tax.relief_krw > 0
                  ? `${c.tax(s.tax.total_pct)} · ${c.relief(won(s.tax.relief_krw))}`
                  : c.tax(s.tax.total_pct)
              }
              value={`+ ${won(s.tax.tax_krw)}`}
            />
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
  return <CheckBody b={b} />;
}

type CheckItem = {
  key: string;
  label: string;
  what: string;
  state: string;
  hint: string | null;
  evidence: { doc: string; fetched_at: string | null } | null;
};
type FlowStep = {
  key: string;
  label: string;
  date: string | null;
  estimated: boolean;
  done: boolean;
};
const STATE_CHIP: Record<string, string> = {
  "확인 완료": "green",
  미확인: "gray",
  "자료 충돌": "orange",
  "전문가 확인 필요": "orange",
};

// 올해는 「6/25」, 다른 해는 「25.6/25」
function flowDate(d: string): string {
  const md = `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
  return d.slice(0, 4) === String(new Date().getFullYear()) ? md : `${d.slice(2, 4)}.${md}`;
}

// ITEM-06: 사건 흐름 막대 + 체크리스트(끝난 것은 접음) + 사건 문건
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CheckBody({ b }: { b: Record<string, any> }) {
  const [showDone, setShowDone] = useState(false);
  const list = b.checklist as CheckItem[];
  const todo = list.filter((x) => x.state !== "확인 완료");
  const done = list.filter((x) => x.state === "확인 완료");
  const flow = b.flow as FlowStep[];
  return (
    <>
      <div style={{ display: "flex", overflowX: "auto", gap: 0, padding: "4px 0 12px" }}>
        {flow.map((f, i) => (
          <div
            key={f.key}
            style={{ flex: "0 0 auto", minWidth: 64, textAlign: "center", fontSize: 11 }}
          >
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{ flex: 1, height: 2, background: i ? "var(--line)" : "transparent" }} />
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: f.done
                    ? "var(--green)"
                    : f.key === "now"
                      ? "var(--blue)"
                      : "var(--line)",
                }}
              />
              <span
                style={{
                  flex: 1,
                  height: 2,
                  background: i < flow.length - 1 ? "var(--line)" : "transparent",
                }}
              />
            </div>
            <div style={{ marginTop: 4, fontWeight: f.key === "now" ? 700 : 400 }}>{f.label}</div>
            <div className="sub" style={{ margin: 0, fontSize: 11 }}>
              {f.date ? flowDate(f.date) : "-"}
              {f.estimated && f.date ? ` ${t.flowGuess}` : ""}
            </div>
          </div>
        ))}
      </div>
      {todo.map((x) => (
        <div key={x.key} style={{ padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`chip ${STATE_CHIP[x.state] ?? "gray"}`}>{x.state}</span>
            <b style={{ fontSize: 14 }}>{x.label}</b>
          </div>
          <div className="sub" style={{ margin: "2px 0 0", fontSize: 12 }}>
            {x.what}
            {x.hint ? ` · ${x.hint}` : ""}
          </div>
        </div>
      ))}
      {done.length > 0 && (
        <button
          onClick={() => setShowDone(!showDone)}
          style={{
            border: 0,
            background: "none",
            color: "var(--muted)",
            fontSize: 13,
            padding: "10px 0",
            minHeight: 44,
          }}
        >
          ✓ {t.doneFold(done.length)} {showDone ? "⌃" : "›"}
        </button>
      )}
      {showDone &&
        done.map((x) => (
          <div key={x.key} style={{ fontSize: 13, padding: "4px 0" }}>
            <span style={{ color: "var(--green)" }}>✓</span> {x.label}
            <span className="sub" style={{ margin: 0 }}>
              {" "}
              · {x.evidence ? t.gotAt(x.evidence.doc, x.evidence.fetched_at) : ""}
            </span>
          </div>
        ))}
      {b.events.length > 0 && (
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 10 }}>{t.events}</div>
      )}
      {b.events
        .slice(0, 6)
        .map((e: { date: string; category: string; after_deadline: boolean }, i: number) => (
          <div key={i} style={{ fontSize: 13, padding: "4px 0" }}>
            <span className="sub" style={{ margin: 0 }}>
              {e.date}
            </span>{" "}
            {e.category}
            {e.after_deadline && <b style={{ color: "var(--amber)" }}> · {t.afterDeadline}</b>}
          </div>
        ))}
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
