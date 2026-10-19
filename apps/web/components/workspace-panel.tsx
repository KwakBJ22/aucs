"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { fetchItem, type ItemDetail } from "@/lib/api/items";
import { meApi, WATCH_STEPS, type WatchStep, type Workspace } from "@/lib/api/me";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

const t = copy.ws;
export const MOVABLE: WatchStep[] = WATCH_STEPS.filter((s) => s !== "result");
type Check = { key: string; label: string; what: string; state: string };
type Tab = "memo" | "checks" | "calcs" | "history";

// 물건 작업 공간(WATCH-02). 휴대폰은 탭 4개(메모·내 확인·계산·이력), PC는 전부 펼침(all=true).
export function WorkspacePanel({
  id,
  token,
  all = false,
  onStep,
}: {
  id: string;
  token: string;
  all?: boolean;
  onStep?: (s: WatchStep) => void;
}) {
  const [d, setD] = useState<ItemDetail | null>(null);
  const [w, setW] = useState<Workspace | null | "none">(null);
  const [memo, setMemo] = useState("");
  const [memoState, setMemoState] = useState<"" | "saving" | "saved">("");
  const [tab, setTab] = useState<Tab>("memo");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setD(null);
    setW(null);
    fetchItem(id)
      .then(setD)
      .catch(() => setD(null));
    meApi
      .workspace(token, id)
      .then((x) => {
        setW(x);
        setMemo(x.memo);
      })
      .catch(() => setW("none"));
  }, [token, id]);

  if (w === "none")
    return (
      <section className="section">
        <p className="sub">{t.notWatched}</p>
        <Link href={`/item/${encodeURIComponent(id)}`}>{t.toDetail} ›</Link>
      </section>
    );
  if (!w) return <section className="section" style={{ height: 220, opacity: 0.5 }} />;

  const typeMemo = (v: string) => {
    setMemo(v);
    setMemoState("saving");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      meApi
        .saveMemo(token, id, v)
        .then(() => setMemoState("saved"))
        .catch(() => setMemoState(""));
    }, 800);
  };
  const toggleCheck = (key: string) => {
    const on = !w.checks[key];
    const checks = { ...w.checks };
    if (on) checks[key] = new Date().toISOString().slice(0, 10);
    else delete checks[key];
    setW({ ...w, checks });
    meApi.check(token, id, key, on).catch(() => {});
  };
  const setStep = (step: WatchStep) => {
    setW({ ...w, step });
    onStep?.(step);
    meApi.setStep(token, id, step).catch(() => {});
  };
  const removeCalc = (bid: number) => {
    setW({ ...w, calcs: w.calcs.filter((x) => x.bid_krw !== bid) });
    meApi.removeCalc(token, id, bid).catch(() => {});
  };

  const checkQ = d?.questions.find((q) => q.key === "check");
  const checklist = ((checkQ?.body as { checklist?: Check[] } | undefined)?.checklist ?? []).filter(
    (c) => c.state !== "확인 완료",
  );
  const show = (k: Tab) => all || tab === k;
  const eid = encodeURIComponent(id);

  return (
    <>
      {d && (
        <Link
          href={`/item/${eid}`}
          className="section"
          style={{ display: "block", color: "inherit" }}
        >
          <div className="sub">
            <b style={{ color: "var(--amber)" }}>{dday(d.d_day)}</b> · {d.court} {d.case_no}
          </div>
          <div style={{ fontWeight: 600, marginTop: 4 }}>
            {d.place} {d.building ?? d.usage}
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
            {won(d.min_price_krw)} <span className="sub">{t.toDetail} ›</span>
          </div>
          {d.fatal && <div className="fatal">{d.fatal}</div>}
        </Link>
      )}

      <section className="section">
        <h2>{copy.watch.stepNow}</h2>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          {(w.step === "result" ? (["result", "after"] as WatchStep[]) : MOVABLE).map((s) => (
            <button
              key={s}
              className={`chip ${s === w.step ? "green" : "gray"}`}
              style={{ border: 0, minHeight: 36 }}
              disabled={s === "result"}
              onClick={() => setStep(s)}
            >
              {copy.watch.steps[s]}
            </button>
          ))}
        </div>
        <Link href={`/watch/${eid}/field`} className="menu-row" style={{ marginTop: 6 }}>
          <span>{t.fieldRow}</span>
          <span className="sub">›</span>
        </Link>
      </section>

      {!all && (
        <div className="seg" role="tablist">
          {(["memo", "checks", "calcs", "history"] as Tab[]).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              className={tab === k ? "on" : ""}
              onClick={() => setTab(k)}
            >
              {t.tabs[k]}
            </button>
          ))}
        </div>
      )}

      {show("memo") && (
        <section className="section">
          <h2>
            {t.memo}{" "}
            <span className="sub" style={{ fontWeight: 400 }}>
              {memoState === "saving" ? t.saving : memoState === "saved" ? t.saved : ""}
            </span>
          </h2>
          <textarea
            value={memo}
            onChange={(e) => typeMemo(e.target.value)}
            placeholder={t.memoHint}
            rows={5}
            maxLength={2000}
            className="memo-box"
          />
        </section>
      )}

      {show("checks") && (
        <section className="section">
          <h2>{t.checks}</h2>
          <div className="sub">{t.checksSub}</div>
          {checklist.length === 0 && <div className="sub">{t.checksNone}</div>}
          {checklist.map((c) => {
            const on = Boolean(w.checks[c.key]);
            return (
              <label key={c.key} className="check-row">
                <input type="checkbox" checked={on} onChange={() => toggleCheck(c.key)} />
                <span>
                  <span style={{ fontWeight: 600, opacity: on ? 0.6 : 1 }}>{c.label}</span>
                  <span className="sub" style={{ display: "block" }}>
                    {on ? t.checkedOn(w.checks[c.key] ?? "") : c.what}
                  </span>
                </span>
              </label>
            );
          })}
        </section>
      )}

      {show("calcs") && (
        <section className="section">
          <h2>
            {t.bids} <span className="sub">{t.bidsMax}</span>
          </h2>
          {w.calcs.length === 0 && <div className="sub">{t.bidsEmpty}</div>}
          {w.calcs.map((x) => (
            <div key={x.bid_krw} className="line-row">
              <span>
                <b>{won(x.bid_krw)}</b>
                <span className="sub" style={{ display: "block" }}>
                  {x.cash_krw ? t.cashNeed(won(x.cash_krw)) : ""} · {x.saved_at}
                </span>
              </span>
              <button
                className="chip gray"
                style={{ border: 0, minHeight: 32 }}
                onClick={() => removeCalc(x.bid_krw)}
              >
                {t.remove}
              </button>
            </div>
          ))}
        </section>
      )}

      {show("history") && (
        <section className="section">
          <h2>{t.history}</h2>
          {w.history.length === 0 && <div className="sub">{t.historyEmpty}</div>}
          {w.history.map((h, i) => (
            <div key={i} className="line-row" style={{ fontSize: 14 }}>
              <span>
                <span className="sub">{h.at}</span> · {h.what} {h.change}
              </span>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
