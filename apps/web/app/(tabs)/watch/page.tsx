"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { NeedLogin } from "@/components/need-login";
import { meApi, type WatchCard, type WatchStep } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.watch;
// 관심 목록 단계별(WATCH-01): 서류 검토 → 임장 → 자금 → 입찰 → 결과, 단계 안은 매각기일 가까운 순
const ORDER: WatchStep[] = ["review", "field", "money", "bid", "result"];
const MOVABLE: WatchStep[] = ["review", "field", "money", "bid"];

function StepRow({
  c,
  onMove,
  onCompare,
}: {
  c: WatchCard;
  onMove: (s: WatchStep) => void;
  onCompare: () => void;
}) {
  const [open, setOpen] = useState(false);
  if (c.step === "result")
    return (
      <Link href="/me" className="sub" style={{ display: "block", padding: "0 0 12px 84px" }}>
        {t.resultHint} ›
      </Link>
    );
  return (
    <div style={{ padding: "0 0 12px 84px", display: "flex", gap: 6, flexWrap: "wrap" }}>
      {!open ? (
        <>
          <button className="chip gray" style={{ border: 0 }} onClick={() => setOpen(true)}>
            {t.stepNow} · {t.steps[c.step]} ›
          </button>
          <Link href={`/watch/${encodeURIComponent(c.item_id)}`} className="chip gray">
            {copy.ws.open} ›
          </Link>
          <button
            className={`chip ${c.in_compare ? "green" : "gray"}`}
            style={{ border: 0 }}
            onClick={onCompare}
          >
            {c.in_compare ? copy.compare.added : copy.compare.add}
          </button>
        </>
      ) : (
        MOVABLE.map((s) => (
          <button
            key={s}
            className={`chip ${s === c.step ? "green" : "gray"}`}
            style={{ border: 0, minHeight: 32 }}
            onClick={() => {
              setOpen(false);
              if (s !== c.step) onMove(s);
            }}
          >
            {t.steps[s]}
          </button>
        ))
      )}
    </div>
  );
}

export default function Watch() {
  const { session, ready } = useSession();
  const [list, setList] = useState<WatchCard[] | null>(null);
  const [only, setOnly] = useState<WatchStep | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (session)
      meApi
        .watch(session.access_token)
        .then(setList)
        .catch(() => setList([]));
  }, [session]);

  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.tabs.watch} />;

  const move = (id: string, step: WatchStep) => {
    setList((l) => l?.map((x) => (x.item_id === id ? { ...x, step } : x)) ?? l);
    meApi.setStep(session.access_token, id, step).catch(() => {});
  };
  const toggleCompare = (c: WatchCard) => {
    const on = !c.in_compare;
    if (on && (list?.filter((x) => x.in_compare).length ?? 0) >= 5) {
      setMsg(copy.compare.full(5));
      return;
    }
    setMsg("");
    setList((l) => l?.map((x) => (x.item_id === c.item_id ? { ...x, in_compare: on } : x)) ?? l);
    (on ? meApi.addCompare : meApi.removeCompare)(session.access_token, c.item_id).catch(() => {});
  };
  const inCompare = list?.filter((x) => x.in_compare).length ?? 0;
  const count = (s: WatchStep) => list?.filter((x) => x.step === s).length ?? 0;
  const groups = ORDER.filter((s) => (only ? s === only : count(s) > 0));

  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
        <Link href="/compare" className="chip gray" style={{ minHeight: 32 }}>
          {copy.compare.title} {inCompare} ›
        </Link>
      </div>
      {msg && (
        <div className="sub" style={{ color: "var(--amber)", marginBottom: 6 }}>
          {msg}
        </div>
      )}
      {list && list.length > 0 && (
        <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 4 }}>
          <button
            className={`chip ${only === null ? "green" : "gray"}`}
            style={{ border: 0, minHeight: 32, whiteSpace: "nowrap" }}
            onClick={() => setOnly(null)}
          >
            {t.all} {list.length}
          </button>
          {ORDER.map((s) => (
            <button
              key={s}
              className={`chip ${only === s ? "green" : "gray"}`}
              style={{ border: 0, minHeight: 32, whiteSpace: "nowrap" }}
              onClick={() => setOnly(only === s ? null : s)}
            >
              {t.steps[s]} {count(s)}
            </button>
          ))}
        </div>
      )}
      {list && list.length === 0 && (
        <section className="section">
          <p className="sub">{t.empty}</p>
        </section>
      )}
      {list &&
        groups.map((s) => (
          <section key={s} className="section" style={{ paddingTop: 12, paddingBottom: 0 }}>
            <h2>
              {t.steps[s]} <span className="sub">{count(s)}</span>
            </h2>
            {list
              .filter((x) => x.step === s)
              .map((c) => (
                <div key={c.item_id}>
                  <ItemCard c={c} />
                  <StepRow
                    c={c}
                    onMove={(st) => move(c.item_id, st)}
                    onCompare={() => toggleCompare(c)}
                  />
                </div>
              ))}
          </section>
        ))}
    </main>
  );
}
