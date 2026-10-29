"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchOnbidMarket, type OnbidMarket as OM, type Stat } from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.proMarket;

export function StatTable({
  title,
  rows,
  from = 0,
}: {
  title: string;
  rows: (Stat & { label: string })[];
  from?: number; // 막대 시작 값(공매는 최저가 대비라 80%부터 봐야 차이가 보임)
}) {
  const max = Math.max(100, ...rows.map((r) => r.p50));
  const w = (v: number) => Math.max(2, ((v - from) * 100) / (max - from));
  return (
    <section className="section m-0">
      <h2 className="fs-base">{title}</h2>
      {rows.length === 0 && <div className="sub">{t.none}</div>}
      {rows.map((r) => (
        <div
          key={r.label}
          className="d-grid gap-8 ai-center fs-sm py-4 px-0"
          style={{ gridTemplateColumns: "128px 1fr 72px" }}
        >
          <span className="ellipsis">{r.label}</span>
          <span className="bg-gray-chip r-4 pos-relative" style={{ height: 10 }}>
            <span
              className="pos-absolute bg-blue r-4"
              style={{ inset: 0, width: `${w(r.p50)}%` }}
            />
          </span>
          <span className="ta-right">
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
      <div className="note blue mt-4 mb-12 mx-0">{o.basis}</div>
      <div className="pc-grid g-2x2" style={{ rowGap: 12 }}>
        <StatTable
          from={80}
          title={o.byBidders}
          rows={m.by_bidders.map((r) => ({ ...r, label: r.bidders }))}
        />
        <StatTable
          from={80}
          title={o.byUsage}
          rows={m.by_usage.map((r) => ({
            ...r,
            label: copy.pro.usages[r.usage as keyof typeof copy.pro.usages] ?? t.etc,
          }))}
        />
        <StatTable
          from={80}
          title={o.bySido}
          rows={m.by_sido.map((r) => ({ ...r, label: r.sido ?? t.etc }))}
        />
        <StatTable
          from={80}
          title={t.byFailed}
          rows={m.by_failed.map((r) => ({ ...r, label: t.failed(r.failed) }))}
        />
      </div>
      <section className="section p-0 ox-auto mt-12">
        <div className="pt-14 pb-0 px-14">
          <h2 className="fs-base">{t.cases}</h2>
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
      <div className="sub mt-8">{o.note}</div>
    </>
  );
}
