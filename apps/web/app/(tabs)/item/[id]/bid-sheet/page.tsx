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
            <label style={{ display: "block", marginTop: 10 }}>
              <span className="sub">{t.amount}</span>
              <input
                inputMode="numeric"
                value={text}
                onChange={(e) => {
                  const v = e.target.value.replace(/[^0-9]/g, "");
                  setText(v);
                  setBid(v ? Number(v) * 10_000 : null);
                }}
                style={{
                  width: "100%",
                  fontSize: 22,
                  padding: "10px 12px",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  background: "var(--surface)",
                  color: "var(--text)",
                }}
              />
            </label>
            {chk && (
              <div style={{ marginTop: 10 }}>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{chk.korean}</div>
                <div
                  style={{
                    fontSize: 14,
                    marginTop: 4,
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
                <div className="sub" style={{ marginTop: 6 }}>
                  {t.deposit(won(chk.deposit_krw), chk.resale)}
                </div>
              </div>
            )}
            <button
              className="btn primary"
              style={{ marginTop: 12 }}
              disabled={!canPrint}
              onClick={() => window.print()}
            >
              {t.print}
            </button>
            <div className="sub" style={{ marginTop: 6 }}>
              {t.printHint}
            </div>
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
              <div key={String(label)} className="line-row" style={{ fontSize: 14 }}>
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
          <h2 style={{ textAlign: "center", fontSize: 20 }}>{t.formTitle}</h2>
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
          <div className="sub" style={{ marginTop: 10 }}>
            {t.f.price} {bid ? `· ${chk?.korean ?? ""}` : ""}
          </div>
          <Digits v={bid} />
          <div className="sub" style={{ marginTop: 10 }}>
            {t.f.deposit}
          </div>
          <Digits v={dep} />
          <div style={{ fontSize: 14, marginTop: 10 }}>{t.f.method}</div>
          <div style={{ fontSize: 14, marginTop: 16, textAlign: "right" }}>{t.f.sign}</div>
          <div className="sub" style={{ marginTop: 12 }}>
            {t.f.note}
          </div>
        </section>
      </div>
      {pc && (
        <div className="no-print" style={{ marginTop: 20 }}>
          <h2 style={{ fontSize: 20 }}>{copy.bidDay.title}</h2>
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
