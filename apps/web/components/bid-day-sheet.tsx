"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchBidDay, type BidDay } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.bidDay;
const KEY = (id: string) => `aucs.bidday.${id}`;

// 입찰일 아침(BID-02): 오늘 진행 여부 · 법원·시각·장소 · 보증금 수표 · 준비물 · 아침 재확인 3가지
export function BidDaySheet({ id, wide = false }: { id: string; wide?: boolean }) {
  const [d, setD] = useState<BidDay | null>(null);
  const [done, setDone] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchBidDay(id)
      .then(setD)
      .catch(() => setD(null));
    try {
      setDone(JSON.parse(localStorage.getItem(KEY(id)) ?? "{}"));
    } catch {}
  }, [id]);
  const tick = (k: string) => {
    const next = { ...done, [k]: !done[k] };
    setDone(next);
    try {
      localStorage.setItem(KEY(id), JSON.stringify(next));
    } catch {}
  };
  if (!d) return null;

  const color = d.state === "ok" || d.state === "soon" ? "var(--green)" : "var(--red)";
  const mapUrl = `https://map.kakao.com/?q=${encodeURIComponent(d.court_full)}`;
  const Check = ({ k, label, sub }: { k: string; label: string; sub?: string }) => (
    <label className="d-flex gap-10 py-10 px-0 mh-44">
      <input
        type="checkbox"
        checked={Boolean(done[k])}
        onChange={() => tick(k)}
        className="f-none"
        style={{ width: 20, height: 20 }}
      />
      <span>
        <span className="fw-6" style={{ opacity: done[k] ? 0.5 : 1 }}>
          {label}
        </span>
        {sub && <span className="sub d-block">{sub}</span>}
      </span>
    </label>
  );
  return (
    <div className={wide ? "pc-grid g-5" : ""}>
      <section className="section">
        <div style={{ color, fontWeight: 700 }}>
          {d.state === "ok" || d.state === "soon" ? "● " : "◆ "}
          {d.state_line}
        </div>
        {d.checked_at && <div className="sub">{t.checked(d.checked_at)}</div>}
      </section>
      <section className="section">
        <div className="sub">
          {d.court} {d.case_no}
          {d.item_no > 1 ? ` · ${t.itemNo(d.item_no)}` : ""}
        </div>
        <div className="fs-2xl fw-7 mt-4">{d.time ? t.at(d.time) : t.timeUnknown}</div>
        <div className="mt-4">
          {d.court_full} · {d.place}
        </div>
        <div className="d-flex gap-6 mt-10 f-wrap">
          <a href={mapUrl} target="_blank" rel="noreferrer" className="chip gray mh-36">
            {t.map} ›
          </a>
          {d.tel && (
            <a href={`tel:${d.tel}`} className="chip gray mh-36">
              {t.call(d.tel)}
            </a>
          )}
        </div>
        <div className="sub mt-8">{t.timeNote}</div>
      </section>
      <section className="section">
        <h2>{t.deposit}</h2>
        <div className="fs-3xl fw-7">{won(d.deposit_krw)}</div>
        <div className="sub">
          {t.depositSub(d.deposit_rate_pct, won(d.min_price_krw), d.resale)}
        </div>
      </section>
      <section className="section">
        <h2>{t.bring}</h2>
        {t.items.map(([k, label, sub]) => (
          <Check key={k} k={k} label={label} sub={sub} />
        ))}
      </section>
      <section className="section">
        <h2>{t.recheck}</h2>
        <div className="sub">{t.recheckSub}</div>
        {t.rechecks.map(([k, label, sub]) => (
          <Check key={k} k={k} label={label} sub={sub} />
        ))}
        {!wide && (
          <Link href={`/item/${encodeURIComponent(id)}/bid-sheet`} className="btn primary mt-12">
            {t.toSheet}
          </Link>
        )}
      </section>
    </div>
  );
}
