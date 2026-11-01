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
    <div className="kv">
      <span className="sub m-0">{typeof label === "string" ? <Termed text={label} /> : label}</span>
      <span className="kv-v">{value}</span>
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
      <button className="chip gray b-0 mh-36 mt-10 d-inline-flex" onClick={() => setOpen(true)}>
        {c.open} ›
      </button>
    );
  return (
    <div className="mt-12 pt-10">
      <div className="fs-md fw-6">{c.title}</div>
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
      <div className="sub mt-4 mb-0 mx-0 fs-xs">
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
  const [assume, setAssume] = useState<number | null>(null); // 떠안는 돈(직접 넣음, 원)
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
        assume,
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
  }, [id, bid, homes, first, loan, selling, income, otherMonthly, assume]);

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
    <label className="d-block fs-sm mt-6">
      <span className="sub m-0">{label}</span>
      <input
        inputMode="numeric"
        onChange={(e) => {
          const n = Number(e.target.value.replace(/[^0-9]/g, ""));
          set(n ? n * 10_000 : null);
        }}
        className="w-full fs-base py-8 px-10 b-0 bg-panel r-14"
      />
    </label>
  );
  const s = d?.selected;
  const over = d?.cap_krw != null && s != null && s.bid_krw > d.cap_krw;
  const myCash = prof?.cash ?? null;
  return (
    <div className="mt-12 pt-12">
      <div className="fs-md fw-6">{c.homesQ}</div>
      <div className="d-flex gap-6 mt-6 f-wrap">
        {c.homes.map((label, i) => (
          <button
            key={label}
            className={`chip ${homes === i ? "green" : "gray"} mh-36 b-0`}

            onClick={() => pickHomes(i)}
          >
            {label}
          </button>
        ))}
        {homes === 0 && (
          <label className="fs-sm d-flex ai-center gap-4">
            <input
              type="checkbox"
              checked={first}
              onChange={(e) => toggle("firstTime", e.target.checked)}
            />
            {c.firstTime}
          </label>
        )}
        {homes === 1 && (
          <label className="fs-sm d-flex ai-center gap-4">
            <input
              type="checkbox"
              checked={selling}
              onChange={(e) => toggle("selling", e.target.checked)}
            />
            {c.selling}
          </label>
        )}
      </div>
      {homes === 1 && selling && <div className="sub mt-4 mb-0 mx-0 fs-xs">{c.sellingHint}</div>}
      {d?.assume?.risk && (
        <div className="bg-panel r-14 p-12 mt-12" role="alert">
          <b className="c-red fs-md">{c.assumeTitle}</b>
          <p className="sub fs-sm mt-4 mb-6 mx-0">{c.assumeWhy}</p>
          <label className="d-block fs-sm mt-6">
            <span className="sub m-0">{c.assumeInput}</span>
            <input
              inputMode="numeric"
              placeholder="0"
              onChange={(e) => {
                const v = e.target.value.replace(/[^0-9]/g, "");
                setAssume(v === "" ? null : Number(v) * 10_000); // 0 = 떠안는 돈 없음 확인
              }}
              className="w-full fs-base py-8 px-10 b-0 bg-panel r-14"
            />
          </label>
          {assume == null && <div className="fs-sm mt-6 c-amber">{c.assumeNeed}</div>}
        </div>
      )}
      {d && s && (
        <>
          {d.cases.length > 0 && (
            <div className="d-flex gap-6 mt-12">
              {d.cases.map((x) => (
                <button
                  key={x.key}
                  onClick={() => setBid(x.bid_krw)}
                  className="f-1 py-8 px-4 r-8 b-0 c-inherit fs-xs"
                  style={{
                    background: s.bid_krw === x.bid_krw ? "var(--green-soft)" : "var(--panel)",
                  }}
                >
                  <b className="fs-sm">{c.cases[x.key]}</b>
                  <div>{won(x.bid_krw)}</div>
                  <div className="sub m-0">{c.chance(x.chance)}</div>
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
            className="w-full mt-12"
            aria-label={t.bidTry}
          />
          <div className="fs-2xl fw-7">{won(s.bid_krw)}</div>
          {chk && (
            <div className="fs-sm">
              {chk.korean}
              {chk.level !== "ok" && (
                <div style={{ color: chk.level === "block" ? "var(--red)" : "var(--amber)" }}>
                  {chk.message}
                </div>
              )}
            </div>
          )}
          <div className="mt-8">
            <Row
              label={`${c.loan} · ${c.region[d.cls]} ${s.loan.pct}%`}
              value={
                <>
                  − {won(s.loan_krw)}{" "}
                  <button
                    onClick={() => setEditLoan(!editLoan)}
                    className="b-0 bg-none c-blue fs-sm"
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
                className="w-full fs-base py-8 px-10 b-0 bg-panel r-14"
              />
            )}
            <div className="sub m-0 fs-xs">
              {s.loan.by_dsr && s.dsr ? c.byDsr(s.dsr.rate_pct) : (s.loan.note ?? c.loanHint)}{" "}
              <button onClick={() => setDsrOpen(!dsrOpen)} className="b-0 bg-none c-blue fs-xs">
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
                    <span className="sub d-block m-0 fs-xs">
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
                    <span className="sub d-block m-0 fs-xs">
                      {c.range(won(d.repair.low_krw), won(d.repair.high_krw))}
                      {d.repair.basis === "unknown_age" ? ` · ${c.ageUnknown}` : ""}
                    </span>
                  </>
                }
              />
            )}
            {(s.assume_krw ?? 0) > 0 && (
              <Row label={c.assumeRow} value={<>+ {won(s.assume_krw ?? 0)}</>} />
            )}
            <Row label={<b>{c.cash}</b>} value={<b className="fs-lg">{won(s.cash_krw)}</b>} />
            {myCash && (
              <div
                className="fs-sm ta-right"
                style={{ color: s.cash_krw > myCash ? "var(--amber)" : "var(--muted)" }}
              >
                {c.vsCash(s.cash_krw > myCash, won(Math.abs(s.cash_krw - myCash)))}
              </div>
            )}
            {d.cap_krw != null && (
              <div className="fs-sm mt-6" style={{ color: over ? "var(--red)" : "var(--muted)" }}>
                ◆ {c.cap(won(d.cap_krw))}
              </div>
            )}
            {d.resale && <div className="sub">{t.resale}</div>}
            {d.rent && <RentBox r={d.rent} open={prof?.purpose === "rent"} />}
            <SaveBid id={id} bid={s.bid_krw} cash={s.cash_krw} />
            <Link
              href={`/item/${encodeURIComponent(id)}/bid-sheet?bid=${s.bid_krw}`}
              className="chip gray mh-36 mt-10 ml-6 d-inline-flex"
            >
              {copy.bidDay.toSheet} ›
            </Link>
            <Link
              href={`/item/${encodeURIComponent(id)}/report?bid=${s.bid_krw}`}
              className="chip gray mh-36 mt-10 ml-6 d-inline-flex"
            >
              {copy.report.open} ›
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
  if (done) return <div className="sub mt-8">{m.saved}</div>;
  if (!open)
    return (
      <button className="chip gray b-0 mh-36 mt-10 ml-6" onClick={() => setOpen(true)}>
        {m.open} ›
      </button>
    );
  const field = {
    width: "100%",
    fontSize: 16,
    padding: "8px 10px",
    border: 0,
    borderRadius: 14,
    background: "var(--panel)",
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
    <div className="mt-12 pt-10">
      <div className="fw-6 fs-md">{m.title}</div>
      <div className="sub">{m.hint}</div>
      <div className="d-flex gap-6 mt-8">
        <button
          className={`chip ${!skip ? "green" : "gray"} b-0 mh-36`}

          onClick={() => setSkip(false)}
        >
          {m.bid} · {won(bid)}
        </button>
        <button
          className={`chip ${skip ? "green" : "gray"} b-0 mh-36`}

          onClick={() => setSkip(true)}
        >
          {m.skip}
        </button>
      </div>
      <label className="d-block fs-sm mt-8">
        <span className="sub">{m.max}</span>
        <input
          inputMode="numeric"
          value={max}
          onChange={(e) => setMax(e.target.value)}
          style={field}
        />
      </label>
      <label className="d-block fs-sm mt-8">
        <span className="sub">{m.reason}</span>
        <input
          value={reason}
          maxLength={500}
          onChange={(e) => setReason(e.target.value)}
          style={field}
        />
      </label>
      <button className="btn primary mt-10" style={{ height: 44 }} onClick={save}>
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
      className="chip gray b-0 mh-36 mt-10"
      disabled={done}

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
