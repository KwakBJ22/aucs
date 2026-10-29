"use client";

import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchBidCheck, fetchBidDay, type BidCheck, type BidDay } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { BidDaySheet } from "@/components/bid-day-sheet";
import { useIsPc } from "@/lib/use-pc";
import { won } from "@/lib/format";

const t = copy.bidSheet;
const PLACES = ["천억", "백억", "십억", "억", "천만", "백만", "십만", "만", "천", "백", "십", "일"];

// 금액을 입찰표 칸(천억~일)에 맞춰 한 글자씩. 앞자리 빈칸은 비워 둠.
function Digits({ v }: { v: number | null }) {
  const s = v ? String(v).padStart(12, " ").slice(-12) : " ".repeat(12);
  return (
    <table className="bid-digits">
      <thead>
        <tr>
          {PLACES.map((p) => (
            <th key={p}>{p}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          {s.split("").map((ch, i) => (
            <td key={i}>{ch.trim()}</td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}

function Sheet() {
  const pc = useIsPc();
  const id = decodeURIComponent(String(useParams().id));
  const sp = useSearchParams();
  const [bid, setBid] = useState<number | null>(Number(sp.get("bid")) || null);
  const [text, setText] = useState(
    sp.get("bid") ? String(Math.round(Number(sp.get("bid")) / 10_000)) : "",
  );
  const [day, setDay] = useState<BidDay | null>(null);
  const [chk, setChk] = useState<BidCheck | null>(null);
  const [sure, setSure] = useState(false);

  useEffect(() => {
    fetchBidDay(id)
      .then(setDay)
      .catch(() => setDay(null));
  }, [id]);
  // 글자 칠 때마다 부르지 않고 멈춘 뒤 한 번(10/27)
  useEffect(() => {
    setSure(false);
    if (!bid) return setChk(null);
    let stale = false;
    const h = setTimeout(() => {
      fetchBidCheck(id, bid)
        .then((r) => !stale && setChk(r))
        .catch(() => !stale && setChk(null));
    }, 300);
    return () => {
      stale = true;
      clearTimeout(h);
    };
  }, [id, bid]);

  const canPrint = chk && chk.level !== "block" && (chk.level === "ok" || sure);
  const dep = chk?.deposit_krw ?? day?.deposit_krw ?? null;
  return (
    <main className="page">
      <div className="pc-grid g-40-60">
        <div className="no-print">
          <PageHeader title={t.title} back={`/item/${encodeURIComponent(id)}`} />
          <section className="section">
            <div className="sub">{t.hint}</div>
            <label className="d-block mt-10">
              <span className="sub">{t.amount}</span>
              <input
                inputMode="numeric"
                value={text}
                onChange={(e) => {
                  const v = e.target.value.replace(/[^0-9]/g, "");
                  setText(v);
                  setBid(v ? Number(v) * 10_000 : null);
                }}
                className="w-full fs-2xl py-10 px-12 b-0 r-14 bg-panel c-text"
              />
            </label>
            {chk && (
              <div className="mt-10">
                <div className="fs-lg fw-7">{chk.korean}</div>
                <div
                  className="fs-md mt-4"
                  style={{
                    color:
                      chk.level === "block"
                        ? "var(--red)"
                        : chk.level === "stop"
                          ? "var(--orange)"
                          : "var(--muted)",
                    fontWeight: chk.level === "ok" ? 400 : 700,
                  }}
                >
                  {chk.message}
                </div>
                {chk.level === "stop" && (
                  <label className="big-confirm">
                    <input
                      type="checkbox"
                      checked={sure}
                      onChange={(e) => setSure(e.target.checked)}
                    />
                    {t.sure(won(bid))}
                  </label>
                )}
                <div className="sub mt-6">{t.deposit(won(chk.deposit_krw), chk.resale)}</div>
              </div>
            )}
            <button
              className="btn primary mt-12"

              disabled={!canPrint}
              onClick={() => window.print()}
            >
              {t.print}
            </button>
            <div className="sub mt-6">{t.printHint}</div>
          </section>
          <section className="section">
            <h2>{t.checkTitle}</h2>
            {[
              [Boolean(chk), t.checks.korean],
              [Boolean(chk) && (chk?.level === "ok" || sure), t.checks.double],
              [Boolean(chk), chk?.resale ? t.checks.deposit20 : t.checks.deposit10],
              [Boolean(day?.item_no), t.checks.itemNo(day?.item_no ?? null)],
              [true, t.checks.privacy],
            ].map(([ok, label]) => (
              <div key={String(label)} className="line-row fs-md">
                <span>{label as string}</span>
                <b style={{ color: ok ? "var(--green)" : "var(--faint)" }}>{ok ? "✓" : "—"}</b>
              </div>
            ))}
            <Link href={`/item/${encodeURIComponent(id)}/bid-day`} className="menu-row">
              <span>{copy.bidDay.title}</span>
              <span className="sub">›</span>
            </Link>
          </section>
        </div>

        <section className="section print-area">
          <h2 className="ta-center fs-xl">{t.formTitle}</h2>
          <table className="bid-form">
            <tbody>
              <tr>
                <th>{t.f.court}</th>
                <td>
                  {day?.court_full} {day?.dept}
                </td>
                <th>{t.f.date}</th>
                <td>{day?.sale_date}</td>
              </tr>
              <tr>
                <th>{t.f.caseNo}</th>
                <td>{day?.case_no}</td>
                <th>{t.f.itemNo}</th>
                <td>{day?.item_no}</td>
              </tr>
              <tr>
                <th>{t.f.bidder}</th>
                <td colSpan={3} className="handwrite">
                  {t.f.bidderHint}
                </td>
              </tr>
              <tr>
                <th>{t.f.agent}</th>
                <td colSpan={3} className="handwrite">
                  {t.f.agentHint}
                </td>
              </tr>
            </tbody>
          </table>
          <div className="sub mt-10">
            {t.f.price} {bid ? `· ${chk?.korean ?? ""}` : ""}
          </div>
          <Digits v={bid} />
          <div className="sub mt-10">{t.f.deposit}</div>
          <Digits v={dep} />
          <div className="fs-md mt-10">{t.f.method}</div>
          <div className="fs-md mt-16 ta-right">{t.f.sign}</div>
          <div className="sub mt-12">{t.f.note}</div>
        </section>
      </div>
      {pc && (
        <div className="no-print mt-20">
          <h2 className="fs-xl">{copy.bidDay.title}</h2>
          <div className="sub">{t.dayHint}</div>
          <BidDaySheet id={id} wide />
        </div>
      )}
    </main>
  );
}

export default function BidSheetPage() {
  return (
    <Suspense>
      <Sheet />
    </Suspense>
  );
}
