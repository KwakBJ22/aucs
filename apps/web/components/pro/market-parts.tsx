"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchOnbidMarket, type OnbidMarket as OM, type Stat } from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.proMarket;

export function StatTable({ title, rows }: { title: string; rows: (Stat & { label: string })[] }) {
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

// 공매 탭: 전국 입찰 결과. 낙찰가율은 최저가 대비(100%를 넘는 게 보통) — 경매 숫자와 섞지 않음.
export function OnbidMarket(f: { sido: string; sigungu: string; usage: string[]; months: number }) {
  const [m, setM] = useState<OM | null>(null);
  const { sido, sigungu, usage, months } = f;
  useEffect(() => {
    let stale = false;
    fetchOnbidMarket({ sido: sido || undefined, sigungu: sigungu || undefined, usage, months })
      .then((r) => !stale && setM(r))
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, [sido, sigungu, usage, months]);
  if (!m) return <div className="sub">{copy.pro.loading}</div>;
  const o = t.onbid;
  return (
    <>
      <div className="note blue" style={{ margin: "4px 0 12px" }}>
        {o.basis}
      </div>
      <div className="pc-grid g-2x2" style={{ rowGap: 12 }}>
        <StatTable
          title={o.byBidders}
          rows={m.by_bidders.map((r) => ({ ...r, label: r.bidders }))}
        />
        <StatTable
          title={o.byUsage}
          rows={m.by_usage.map((r) => ({
            ...r,
            label: copy.pro.usages[r.usage as keyof typeof copy.pro.usages] ?? t.etc,
          }))}
        />
        <StatTable
          title={o.bySido}
          rows={m.by_sido.map((r) => ({ ...r, label: r.sido ?? t.etc }))}
        />
        <StatTable
          title={t.byFailed}
          rows={m.by_failed.map((r) => ({ ...r, label: t.failed(r.failed) }))}
        />
      </div>
      <section className="section" style={{ padding: 0, overflowX: "auto", marginTop: 12 }}>
        <div style={{ padding: "14px 14px 0" }}>
          <h2 style={{ fontSize: 15 }}>{t.cases}</h2>
        </div>
        <table className="pro-table">
          <thead>
            <tr>
              {o.cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {m.cases.map((r) => (
              <tr key={`${r.mng_no}${r.sale_date}`}>
                <td>{r.sale_date.slice(5)}</td>
                <td>
                  <Link href={`/item/OB-${r.mng_no}`}>{r.mng_no}</Link>{" "}
                  <span className="sub">{r.kind_name}</span>
                </td>
                <td>{r.usage_name}</td>
                <td>{r.title}</td>
                <td>{won(r.min_price_krw)}</td>
                <td>{won(r.win_krw)}</td>
                <td>
                  <b>{r.rate_min != null ? `${Math.round(r.rate_min)}%` : ""}</b>{" "}
                  <span className="sub">
                    {r.rate_appraisal != null ? o.ofApp(Math.round(r.rate_appraisal)) : ""}
                  </span>
                </td>
                <td>{r.bidders ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <div className="sub" style={{ marginTop: 8 }}>
        {o.note}
      </div>
    </>
  );
}
