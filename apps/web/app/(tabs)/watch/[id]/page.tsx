"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import { fetchItem, type ItemDetail } from "@/lib/api/items";
import { meApi, type WatchStep, type Workspace } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";

const t = copy.ws;
const MOVABLE: WatchStep[] = ["review", "field", "money", "bid"];
type Check = { key: string; label: string; what: string; state: string };

// 물건 작업 공간(WATCH-02): 단계 · 내 확인 · 메모 · 저장한 입찰가 · 바뀐 것
export default function WorkspacePage() {
  const id = decodeURIComponent(String(useParams().id));
  const { session, ready } = useSession();
  const [d, setD] = useState<ItemDetail | null>(null);
  const [w, setW] = useState<Workspace | null | "none">(null);
  const [memo, setMemo] = useState("");
  const [memoState, setMemoState] = useState<"" | "saving" | "saved">("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const token = session?.access_token ?? null;

  useEffect(() => {
    fetchItem(id)
      .then(setD)
      .catch(() => setD(null));
  }, [id]);
  useEffect(() => {
    if (!token) return;
    meApi
      .workspace(token, id)
      .then((x) => {
        setW(x);
        setMemo(x.memo);
      })
      .catch(() => setW("none"));
  }, [token, id]);

  if (!ready) return null;
  if (!session || !token) return <NeedLogin title={t.title} />;
  if (w === "none")
    return (
      <main className="page">
        <section className="section">
          <p className="sub">{t.notWatched}</p>
          <Link href={`/item/${encodeURIComponent(id)}`}>{t.toDetail} ›</Link>
        </section>
      </main>
    );
  if (!w) return <main className="page" />;

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

  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
      </div>
      {d && (
        <Link
          href={`/item/${encodeURIComponent(id)}`}
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

      {w.step !== "result" && (
        <Link
          href={`/watch/${encodeURIComponent(id)}/field`}
          className="btn primary"
          style={{ height: 48, marginBottom: 10 }}
        >
          {copy.field.title} ›
        </Link>
      )}
      {w.step !== "result" && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {MOVABLE.map((s) => (
            <button
              key={s}
              className={`chip ${s === w.step ? "green" : "gray"}`}
              style={{ border: 0, minHeight: 36 }}
              onClick={() => setStep(s)}
            >
              {copy.watch.steps[s]}
            </button>
          ))}
        </div>
      )}

      <section className="section">
        <h2>{t.checks}</h2>
        <div className="sub">{t.checksSub}</div>
        {checklist.map((c) => {
          const on = Boolean(w.checks[c.key]);
          return (
            <label
              key={c.key}
              style={{
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
                padding: "10px 0",
                borderTop: "1px solid var(--line)",
                minHeight: 44,
              }}
            >
              <input
                type="checkbox"
                checked={on}
                onChange={() => toggleCheck(c.key)}
                style={{ width: 20, height: 20, marginTop: 2 }}
              />
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
          style={{
            width: "100%",
            marginTop: 8,
            fontSize: 16,
            padding: 10,
            border: "1px solid var(--line)",
            borderRadius: 10,
            background: "var(--surface)",
            color: "var(--text)",
            resize: "vertical",
          }}
        />
      </section>

      <section className="section">
        <h2>{t.bids}</h2>
        {w.calcs.length === 0 && <div className="sub">{t.bidsEmpty}</div>}
        {w.calcs.map((x) => (
          <div
            key={x.bid_krw}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "10px 0",
              borderTop: "1px solid var(--line)",
            }}
          >
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

      <section className="section">
        <h2>{t.history}</h2>
        {w.history.length === 0 && <div className="sub">{t.historyEmpty}</div>}
        {w.history.map((h, i) => (
          <div
            key={i}
            style={{ padding: "8px 0", borderTop: "1px solid var(--line)", fontSize: 14 }}
          >
            <span className="sub">{h.at}</span> · {h.what} {h.change}
          </div>
        ))}
      </section>
    </main>
  );
}
