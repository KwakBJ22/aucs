"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchRegions, type RegionRow } from "@/lib/api/items";
import { fetchMarket, type Market, type Stat } from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.proMarket;
const MIN_SCORE = 20; // 이보다 적으면 성적을 말하지 않음

function StatTable({ title, rows }: { title: string; rows: (Stat & { label: string })[] }) {
  const max = Math.max(100, ...rows.map((r) => r.p50));
  return (
    <section className="section" style={{ margin: 0 }}>
      <h2 style={{ fontSize: 15 }}>{title}</h2>
      {rows.length === 0 && <div className="sub">{t.none}</div>}
      {rows.map((r) => (
        <div
          key={r.label}
          style={{
            display: "grid",
            gridTemplateColumns: "88px 1fr 64px",
            gap: 8,
            alignItems: "center",
            fontSize: 13,
            padding: "4px 0",
          }}
        >
          <span>{r.label}</span>
          <span
            style={{
              background: "var(--gray-chip)",
              borderRadius: 4,
              height: 10,
              position: "relative",
            }}
          >
            <span
              style={{
                position: "absolute",
                inset: 0,
                width: `${(r.p50 * 100) / max}%`,
                background: "var(--blue)",
                borderRadius: 4,
              }}
            />
          </span>
          <span style={{ textAlign: "right" }}>
            <b>{Math.round(r.p50)}%</b> <span className="sub">{r.n}</span>
          </span>
        </div>
      ))}
    </section>
  );
}

export default function ProMarketPage() {
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [usage, setUsage] = useState<string[]>([]);
  const [months, setMonths] = useState(3);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [m, setM] = useState<Market | null>(null);

  useEffect(() => {
    fetchRegions()
      .then(setRegions)
      .catch(() => {});
  }, []);
  useEffect(() => {
    setM(null);
    fetchMarket({ sido: sido || undefined, sigungu: sigungu || undefined, usage, months })
      .then(setM)
      .catch(() => {});
  }, [sido, sigungu, usage, months]);

  const sel = {
    fontSize: 14,
    padding: "6px 8px",
    border: "1px solid var(--line)",
    borderRadius: 8,
    background: "var(--surface)",
    color: "var(--text)",
  };
  const sc = m?.scorecard;
  return (
    <main className="page pro-page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
      </div>
      <section className="section pro-filters">
        <div className="pro-row">
          <select
            value={sido}
            onChange={(e) => (setSido(e.target.value), setSigungu(""))}
            style={sel}
          >
            <option value="">{copy.pro.allSido}</option>
            <option value="서울특별시">서울</option>
            <option value="경기도">경기</option>
          </select>
          <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} style={sel}>
            <option value="">{copy.pro.allSigungu}</option>
            {regions
              .filter((r) => !sido || r.sido === sido)
              .map((r) => (
                <option key={`${r.sido}${r.sigungu}`} value={r.sigungu}>
                  {r.sigungu}
                </option>
              ))}
          </select>
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} style={sel}>
            {[1, 3, 6, 12].map((x) => (
              <option key={x} value={x}>
                {t.months(x)}
              </option>
            ))}
          </select>
        </div>
        <div className="pro-row">
          <span className="sub">{copy.pro.usage}</span>
          {Object.entries(copy.pro.usages).map(([k, v]) => (
            <button
              key={k}
              className={`chip ${usage.includes(k) ? "green" : "gray"}`}
              style={{ border: 0, minHeight: 30 }}
              onClick={() =>
                setUsage(usage.includes(k) ? usage.filter((x) => x !== k) : [...usage, k])
              }
            >
              {v}
            </button>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 style={{ fontSize: 15 }}>{t.score}</h2>
        {!sc ? (
          <div className="sub">{copy.pro.loading}</div>
        ) : sc.n < MIN_SCORE ? (
          <div className="sub">{t.scoreWait(sc.n, MIN_SCORE)}</div>
        ) : (
          <div style={{ fontSize: 15 }}>
            {t.scoreLine(Math.round((sc.inside * 100) / sc.n), sc.n)}{" "}
            <span className="sub">
              {t.scoreSplit(
                Math.round((sc.below * 100) / sc.n),
                Math.round((sc.above * 100) / sc.n),
              )}
            </span>
          </div>
        )}
        <div className="sub" style={{ marginTop: 4 }}>
          {t.scoreNote}
        </div>
      </section>

      {m && (
        <div className="stat-grid">
          <StatTable title={t.byCourt} rows={m.by_court.map((r) => ({ ...r, label: r.court }))} />
          <StatTable
            title={t.byFailed}
            rows={m.by_failed.map((r) => ({ ...r, label: t.failed(r.failed) }))}
          />
          <StatTable title={t.byMonth} rows={m.by_month.map((r) => ({ ...r, label: r.month }))} />
        </div>
      )}

      <section className="section" style={{ padding: 0, overflowX: "auto", marginTop: 12 }}>
        <div style={{ padding: "14px 14px 0" }}>
          <h2 style={{ fontSize: 15 }}>{t.cases}</h2>
        </div>
        <table className="pro-table">
          <thead>
            <tr>
              {t.cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {m?.cases.map((r) => (
              <tr key={`${r.court}${r.case_no}${r.sale_date}${r.address}`}>
                <td>{r.sale_date.slice(5)}</td>
                <td>
                  {r.item_id ? (
                    <Link href={`/item/${encodeURIComponent(r.item_id)}`}>
                      {r.court} {r.case_no}
                    </Link>
                  ) : (
                    `${r.court} ${r.case_no}`
                  )}
                </td>
                <td>{r.usage_name}</td>
                <td>{r.address}</td>
                <td>{r.building_area_m2 ? `${Math.round(r.building_area_m2)}㎡` : ""}</td>
                <td>{won(r.appraisal_krw)}</td>
                <td>{won(r.winning_bid_krw)}</td>
                <td>
                  <b>{Math.round(r.sale_rate)}%</b>
                </td>
                <td>{r.failed_count ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <div className="sub" style={{ marginTop: 8 }}>
        {t.note}
      </div>
    </main>
  );
}
