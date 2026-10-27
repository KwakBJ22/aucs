"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { fetchCalc, type BidCheck, type Calc } from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { useWatch } from "@/components/watch-context";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { loadProfile, saveProfile } from "@/lib/profile";
import { track } from "@/lib/track";
import { Termed } from "@/components/term";

const t = copy.item;

export function Row({ label, value }: { label: React.ReactNode; value: React.ReactNode }) {
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
        {typeof label === "string" ? <Termed text={label} /> : label}
      </span>
      <span style={{ textAlign: "right" }}>{value}</span>
    </div>
  );
}

// 입찰가 계산(CALC-01): 집 수 → 세 경우 → 슬라이더 → 필요한 현금. 금액은 한글로도 읽어 줍니다.
// 세놓으면(옥스 기능 9, 10/27): 같은 단지 1년 전월세 가운데 값. 「세를 놓을 거예요」로 답한 사람은 펼쳐서
function RentBox({ r, open: start }: { r: NonNullable<Calc["rent"]>; open: boolean }) {
  const c = t.calc.rent;
  const [open, setOpen] = useState(start);
  if (!open)
    return (
      <button
        className="chip gray"
        style={{ border: 0, minHeight: 36, marginTop: 10, display: "inline-flex" }}
        onClick={() => setOpen(true)}
      >
        {c.open} ›
      </button>
    );
  return (
    <div style={{ marginTop: 12, borderTop: "1px dashed var(--line)", paddingTop: 10 }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>{c.title}</div>
      {r.jeonse && (
        <Row
          label={c.jeonse(won(r.jeonse.deposit_krw), r.jeonse_n)}
          value={c.tied(won(r.jeonse.cash_krw))}
        />
      )}
      {r.wolse && (
        <>
          <Row
            label={c.wolse(won(r.wolse.deposit_krw), won(r.wolse.rent_krw), r.wolse_n)}
            value={c.tied(won(r.wolse.cash_krw))}
          />
          <Row
            label={c.net}
            value={
              <b>
                {won(r.wolse.net_year_krw)}
                {r.wolse.yield_pct != null ? ` · ${c.yieldPct(r.wolse.yield_pct)}` : ""}
              </b>
            }
          />
        </>
      )}
      <div className="sub" style={{ margin: "4px 0 0", fontSize: 12 }}>
        {r.no_loan_reason ? c.noLoan : c.withLoan(r.rate_pct)} · {c.basis}
      </div>
    </div>
  );
}

export function CalcBox({ id }: { id: string }) {
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

  // 계산과 입찰표 검사를 한 번에 받음. 처음 받은 추천 입찰가로 같은 계산을 또 부르지 않음(10/27)
  const fromServer = useRef<number | null>(null);
  const tracked = useRef(false); // 계산을 처음 열었을 때 한 번만 기록
  useEffect(() => {
    if (homes == null) return;
    if (bid != null && bid === fromServer.current) {
      fromServer.current = null; // 다음 바꿈부터는 다시 부름
      return;
    }
    const h = setTimeout(() => {
      if (!tracked.current) {
        tracked.current = true;
        track("calc", id);
      }
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
          setChk(r.check ?? null);
          if (bid == null) {
            fromServer.current = r.selected.bid_krw;
            setBid(r.selected.bid_krw);
          }
        })
        .catch(() => setD(null));
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
            {d.move_out && s.move_out_krw > 0 && (
              <Row
                label={c.moveOut}
                value={
                  <>
                    + {won(s.move_out_krw)}
                    <span className="sub" style={{ display: "block", margin: 0, fontSize: 12 }}>
                      {c.range(won(d.move_out.low_krw), won(d.move_out.high_krw))}
                      {d.move_out.stairs ? ` · ${c.stairs}` : ""}
                    </span>
                  </>
                }
              />
            )}
            {d.repair && s.repair_krw > 0 && (
              <Row
                label={c.repair}
                value={
                  <>
                    + {won(s.repair_krw)}
                    <span className="sub" style={{ display: "block", margin: 0, fontSize: 12 }}>
                      {c.range(won(d.repair.low_krw), won(d.repair.high_krw))}
                      {d.repair.basis === "unknown_age" ? ` · ${c.ageUnknown}` : ""}
                    </span>
                  </>
                }
              />
            )}
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
            {d.rent && <RentBox r={d.rent} open={prof?.purpose === "rent"} />}
            <SaveBid id={id} bid={s.bid_krw} cash={s.cash_krw} />
            <Link
              href={`/item/${encodeURIComponent(id)}/bid-sheet?bid=${s.bid_krw}`}
              className="chip gray"
              style={{ minHeight: 36, marginTop: 10, marginLeft: 6, display: "inline-flex" }}
            >
              {copy.bidDay.toSheet} ›
            </Link>
            <MockForm id={id} bid={s.bid_krw} />
          </div>
        </>
      )}
    </div>
  );
}

// 모의입찰(내 분석 노트): 들어간다면 얼마·내 상한·이유, 또는 안 들어감
function MockForm({ id, bid }: { id: string; bid: number }) {
  const m = copy.mock;
  const { session } = useSession();
  const [open, setOpen] = useState(false);
  const [skip, setSkip] = useState(false);
  const [max, setMax] = useState("");
  const [reason, setReason] = useState("");
  const [done, setDone] = useState(false);
  if (!session) return null;
  if (done)
    return (
      <div className="sub" style={{ marginTop: 8 }}>
        {m.saved}
      </div>
    );
  if (!open)
    return (
      <button
        className="chip gray"
        style={{ border: 0, minHeight: 36, marginTop: 10, marginLeft: 6 }}
        onClick={() => setOpen(true)}
      >
        {m.open} ›
      </button>
    );
  const field = {
    width: "100%",
    fontSize: 16,
    padding: "8px 10px",
    border: "1px solid var(--line)",
    borderRadius: 8,
    background: "var(--surface)",
    color: "var(--text)",
  };
  const save = () =>
    meApi
      .saveMock(session.access_token, {
        item_id: id,
        decision: skip ? "skip" : "bid",
        bid_krw: skip ? null : bid,
        max_krw: Number(max.replace(/[^0-9]/g, "")) * 10_000 || null,
        reason: reason.trim() || null,
      })
      .then(() => setDone(true))
      .catch(() => {});
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
      <div style={{ fontWeight: 600, fontSize: 14 }}>{m.title}</div>
      <div className="sub">{m.hint}</div>
      <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
        <button
          className={`chip ${!skip ? "green" : "gray"}`}
          style={{ border: 0, minHeight: 36 }}
          onClick={() => setSkip(false)}
        >
          {m.bid} · {won(bid)}
        </button>
        <button
          className={`chip ${skip ? "green" : "gray"}`}
          style={{ border: 0, minHeight: 36 }}
          onClick={() => setSkip(true)}
        >
          {m.skip}
        </button>
      </div>
      <label style={{ display: "block", fontSize: 13, marginTop: 8 }}>
        <span className="sub">{m.max}</span>
        <input
          inputMode="numeric"
          value={max}
          onChange={(e) => setMax(e.target.value)}
          style={field}
        />
      </label>
      <label style={{ display: "block", fontSize: 13, marginTop: 8 }}>
        <span className="sub">{m.reason}</span>
        <input
          value={reason}
          maxLength={500}
          onChange={(e) => setReason(e.target.value)}
          style={field}
        />
      </label>
      <button className="btn primary" style={{ height: 44, marginTop: 10 }} onClick={save}>
        {m.save}
      </button>
    </div>
  );
}

// 관심 담은 물건이면 지금 입찰가를 작업 공간에 저장(WATCH-02)
function SaveBid({ id, bid, cash }: { id: string; bid: number; cash: number }) {
  const { ids, token } = useWatch();
  const [saved, setSaved] = useState<number | null>(null);
  if (!token || !ids.has(id)) return null;
  const done = saved === bid;
  return (
    <button
      className="chip gray"
      disabled={done}
      style={{ border: 0, minHeight: 36, marginTop: 10 }}
      onClick={() =>
        meApi
          .addCalc(token, id, bid, cash)
          .then(() => setSaved(bid))
          .catch(() => {})
      }
    >
      {done ? copy.ws.bidSaved : copy.ws.saveBid}
    </button>
  );
}
