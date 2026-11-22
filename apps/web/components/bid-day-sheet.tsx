"use client";

import { Delayed, SkLines, SkRows } from "@/components/skeleton";
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
  if (!d)
    return (
      <Delayed>
        <section className="section">
          <SkLines n={2} />
        </section>
        <section className="section">
          <SkRows n={5} />
        </section>
      </Delayed>
    );

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
  // PC 입찰표 아래 한 장(11/22 디자인): 날짜 한 줄 + 상태 꼬리표, 네 칸(법원 · 보증금 수표 · 챙길 것 · 출발 전 확인)
  if (wide) {
    const dt = d.sale_date ? new Date(`${d.sale_date}T00:00:00+09:00`) : null;
    const today = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
    today.setHours(0, 0, 0, 0);
    const left = dt ? Math.round((dt.getTime() - today.getTime()) / 864e5) : null;
    return (
      <>
        <div className="d-flex jc-between ai-start gap-12 f-wrap">
          <h2 className="bd-title">
            {dt
              ? t.dateLine(dt.getMonth() + 1, dt.getDate(), "일월화수목금토"[dt.getDay()] ?? "")
              : t.timeUnknown}
            {left === 0 ? ` · ${t.todayBid}` : left === 1 ? ` · ${t.tomorrowBid}` : ""}
          </h2>
          <span className={`chip ${d.state === "ok" || d.state === "soon" ? "green" : "red"}`}>
            {d.state_line}
            {d.checked_at ? ` · ${t.checked(d.checked_at)}` : ""}
          </span>
        </div>
        <div className="bd-tiles">
          <div>
            <p className="sub m-0">{copy.bidSheet.f.court}</p>
            <b className="bd-big">{d.court_full}</b>
            <p className="fs-md mt-6 mb-0">
              {d.place}
              <br />
              {d.time ? t.at(d.time) : t.timeUnknown}
            </p>
            <div className="d-flex gap-12 f-wrap">
              <a href={mapUrl} target="_blank" rel="noreferrer" className="link">
                {t.map}
              </a>
              {d.tel && (
                <a href={`tel:${d.tel}`} className="link">
                  {t.call(d.tel)}
                </a>
              )}
            </div>
          </div>
          <div className="bd-dep">
            <p className="m-0">{t.deposit}</p>
            <b>{won(d.deposit_krw)}</b>
            <p className="fs-md mt-6 mb-0">
              {t.depositSub(d.deposit_rate_pct, won(d.min_price_krw), d.resale)}
            </p>
          </div>
          <div>
            <p className="sub m-0">{t.bring}</p>
            {t.items.map(([k, label]) => (
              <Check key={k} k={k} label={label} />
            ))}
          </div>
          <div>
            <p className="sub m-0">{t.recheck}</p>
            {t.rechecks.map(([k, label]) => (
              <Check key={k} k={k} label={label} />
            ))}
          </div>
        </div>
        <p className="sub mt-14 mb-0">{t.timeNote}</p>
      </>
    );
  }
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
          <a href={mapUrl} target="_blank" rel="noreferrer" className="link">
            {t.map}
          </a>
          {d.tel && (
            <a href={`tel:${d.tel}`} className="link">
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
