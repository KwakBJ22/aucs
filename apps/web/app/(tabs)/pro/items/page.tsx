"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { fetchRegions, type RegionRow } from "@/lib/api/items";
import {
  fetchPro,
  fromQuery,
  proCsvUrl,
  toQuery,
  type ProFilter,
  type ProResult,
  type ProRow,
} from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { PickPanel } from "@/components/pick-panel";
import { useIsPc } from "@/lib/use-pc";
import { dday, won } from "@/lib/format";

const t = copy.pro;
type ColKey = keyof typeof t.cols;
const ALL_COLS = Object.keys(t.cols) as ColKey[];
const DEFAULT_COLS: ColKey[] = [
  "case",
  "usage",
  "address",
  "area",
  "appraisal",
  "min",
  "failed",
  "date",
  "market",
  "signal",
];
const COLS_KEY = "aucs.pro.cols";

function cell(r: ProRow, k: ColKey): React.ReactNode {
  switch (k) {
    case "case":
      return (
        <Link href={`/item/${encodeURIComponent(r.item_id)}`}>
          {r.court} {r.case_no}
          {r.item_no > 1 ? `-${r.item_no}` : ""}
        </Link>
      );
    case "usage":
      return r.usage;
    case "address":
      return r.address;
    case "area":
      return r.area_m2 ? `${Math.round(r.area_m2)}㎡` : "";
    case "appraisal":
      return won(r.appraisal_krw);
    case "min":
      return (
        <>
          {won(r.min_price_krw)} <span className="sub">{r.min_rate}%</span>
        </>
      );
    case "failed":
      return r.failed_count ?? 0;
    case "date":
      return (
        <>
          {r.sale_date?.slice(5)} <span className="sub">{dday(r.d_day)}</span>
        </>
      );
    case "market":
      return r.market_krw ? won(r.market_krw) : "";
    case "signal":
      return r.signal ? (
        <span style={{ color: r.fatal ? "var(--red)" : "var(--orange)" }}>{r.signal}</span>
      ) : (
        ""
      );
  }
}

function ProItems() {
  const router = useRouter();
  const sp = useSearchParams();
  const f = useMemo(() => fromQuery(new URLSearchParams(sp.toString())), [sp]);
  const [data, setData] = useState<ProResult | null>(null);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [cols, setCols] = useState<ColKey[]>(DEFAULT_COLS);
  const [colOpen, setColOpen] = useState(false);
  const [qText, setQText] = useState(f.q ?? "");
  const [pick, setPick] = useState<string | null>(null);
  const pc = useIsPc();

  useEffect(() => {
    fetchRegions()
      .then(setRegions)
      .catch(() => {});
    try {
      const saved = JSON.parse(localStorage.getItem(COLS_KEY) ?? "null") as ColKey[] | null;
      if (saved?.length) setCols(saved.filter((c) => ALL_COLS.includes(c)));
    } catch {}
  }, []);
  useEffect(() => {
    setData(null);
    fetchPro(f)
      .then(setData)
      .catch(() =>
        setData({
          rows: [],
          summary: { n: 0, app_sum: 0, app_avg: 0, app_max: 0, min_sum: 0, all: 0 },
          page: 1,
          limit: 50,
        }),
      );
  }, [f]);

  // 조건이 바뀌면 주소창에 그대로 남김(그 주소를 저장·공유하면 같은 조건)
  const set = (patch: Partial<ProFilter>) => {
    const next = { ...f, ...patch, page: patch.page ?? undefined };
    router.replace(`/pro/items?${toQuery(next)}`);
  };
  const toggle = (k: "usage" | "exclude", v: string) => {
    const cur = f[k] ?? [];
    set({ [k]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] });
  };
  const toggleCol = (c: ColKey) => {
    const next = cols.includes(c)
      ? cols.filter((x) => x !== c)
      : ALL_COLS.filter((x) => x === c || cols.includes(x));
    setCols(next);
    try {
      localStorage.setItem(COLS_KEY, JSON.stringify(next));
    } catch {}
  };
  const num = (v: string) => (v === "" ? undefined : Number(v));
  const sigungus = regions.filter((r) => !f.sido || r.sido === f.sido);
  const s = data?.summary;
  const page = f.page ?? 1;
  const pages = s ? Math.max(1, Math.ceil(s.n / (data?.limit ?? 50))) : 1;
  const sel = {
    fontSize: 14,
    padding: "6px 8px",
    border: "1px solid var(--line)",
    borderRadius: 8,
    background: "var(--surface)",
    color: "var(--text)",
  };

  return (
    <main className="page pro-page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
        <a href={proCsvUrl(f)} className="chip gray" style={{ minHeight: 32 }}>
          {t.csv}
        </a>
      </div>
      <div className="pc-hint sub">{t.pcHint}</div>

      <section className="section pro-filters">
        <div className="pro-row">
          <select
            value={f.sido ?? ""}
            onChange={(e) => set({ sido: e.target.value || undefined, sigungu: undefined })}
            style={sel}
          >
            <option value="">{t.allSido}</option>
            <option value="서울특별시">서울</option>
            <option value="경기도">경기</option>
          </select>
          <select
            value={f.sigungu ?? ""}
            onChange={(e) => set({ sigungu: e.target.value || undefined })}
            style={sel}
          >
            <option value="">{t.allSigungu}</option>
            {sigungus.map((r) => (
              <option key={`${r.sido}${r.sigungu}`} value={r.sigungu}>
                {r.sigungu} ({r.items})
              </option>
            ))}
          </select>
          <input
            placeholder={t.search}
            value={qText}
            onChange={(e) => setQText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && set({ q: qText || undefined })}
            style={{ ...sel, minWidth: 180 }}
          />
          <select
            value={f.sort ?? "deadline"}
            onChange={(e) => set({ sort: e.target.value })}
            style={sel}
          >
            {Object.entries(t.sorts).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className="pro-row">
          <span className="sub">{t.usage}</span>
          {Object.entries(t.usages).map(([k, v]) => (
            <button
              key={k}
              className={`chip ${f.usage?.includes(k) ? "green" : "gray"}`}
              style={{ border: 0, minHeight: 30 }}
              onClick={() => toggle("usage", k)}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="pro-row">
          <span className="sub">{t.failed}</span>
          <input
            type="number"
            min={0}
            value={f.failed_min ?? ""}
            onChange={(e) => set({ failed_min: num(e.target.value) })}
            style={{ ...sel, width: 64 }}
          />
          ~
          <input
            type="number"
            min={0}
            value={f.failed_max ?? ""}
            onChange={(e) => set({ failed_max: num(e.target.value) })}
            style={{ ...sel, width: 64 }}
          />
          <span className="sub">{t.appraisal}</span>
          <input
            type="number"
            min={0}
            value={f.app_min ?? ""}
            onChange={(e) => set({ app_min: num(e.target.value) })}
            style={{ ...sel, width: 72 }}
          />
          ~
          <input
            type="number"
            min={0}
            value={f.app_max ?? ""}
            onChange={(e) => set({ app_max: num(e.target.value) })}
            style={{ ...sel, width: 72 }}
          />
          <span className="sub">{t.eok}</span>
          <select
            value={f.rate_max ?? ""}
            onChange={(e) => set({ rate_max: num(e.target.value) })}
            style={sel}
          >
            <option value="">{t.rateAny}</option>
            {[80, 70, 60, 50, 40].map((x) => (
              <option key={x} value={x}>
                {t.rateMax(x)}
              </option>
            ))}
          </select>
          <select
            value={f.days_max ?? ""}
            onChange={(e) => set({ days_max: num(e.target.value) })}
            style={sel}
          >
            <option value="">{t.daysAny}</option>
            {[3, 7, 14, 30].map((x) => (
              <option key={x} value={x}>
                {t.daysMax(x)}
              </option>
            ))}
          </select>
        </div>
        <div className="pro-row">
          <span className="sub">{t.exclude}</span>
          {Object.entries(t.excludes).map(([k, v]) => (
            <button
              key={k}
              className={`chip ${f.exclude?.includes(k) ? "orange" : "gray"}`}
              style={{ border: 0, minHeight: 30 }}
              onClick={() => toggle("exclude", k)}
            >
              {v}
            </button>
          ))}
        </div>
      </section>

      {s && (
        <div className="pro-summary">
          <div>
            <b>{s.n.toLocaleString("ko-KR")}</b>
            <span className="sub">{t.sum.n}</span>
          </div>
          <div>
            <b>{won(s.app_sum)}</b>
            <span className="sub">{t.sum.appSum}</span>
          </div>
          <div>
            <b>{won(s.app_avg)}</b>
            <span className="sub">{t.sum.appAvg}</span>
          </div>
          <div>
            <b>{won(s.app_max)}</b>
            <span className="sub">{t.sum.appMax}</span>
          </div>
          <div>
            <b>{won(s.min_sum)}</b>
            <span className="sub">{t.sum.minSum}</span>
          </div>
          <div>
            <b>{s.all ? Math.round((s.n * 100) / s.all) : 0}%</b>
            <span className="sub">{t.sum.share(s.all.toLocaleString("ko-KR"))}</span>
          </div>
        </div>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          margin: "8px 0",
        }}
      >
        <div style={{ position: "relative" }}>
          <button
            className="chip gray"
            style={{ border: 0, minHeight: 30 }}
            onClick={() => setColOpen(!colOpen)}
          >
            {t.colPick} ›
          </button>
          {colOpen && (
            <div
              className="section"
              style={{
                position: "absolute",
                zIndex: 5,
                margin: 0,
                padding: 10,
                boxShadow: "0 4px 16px rgba(0,0,0,.15)",
              }}
            >
              {ALL_COLS.map((c) => (
                <label
                  key={c}
                  style={{
                    display: "flex",
                    gap: 6,
                    fontSize: 14,
                    padding: "3px 0",
                    whiteSpace: "nowrap",
                  }}
                >
                  <input type="checkbox" checked={cols.includes(c)} onChange={() => toggleCol(c)} />
                  {t.cols[c]}
                </label>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <button
            className="chip gray"
            style={{ border: 0, minHeight: 30 }}
            disabled={page <= 1}
            onClick={() => set({ page: page - 1 })}
          >
            ‹
          </button>
          <span className="sub">
            {page} / {pages}
          </span>
          <button
            className="chip gray"
            style={{ border: 0, minHeight: 30 }}
            disabled={page >= pages}
            onClick={() => set({ page: page + 1 })}
          >
            ›
          </button>
        </div>
      </div>

      <div className={pc ? "pc-grid g-58-42" : ""}>
      <section className="section" style={{ padding: 0, overflowX: "auto" }}>
        <table className="pro-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{t.cols[c]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!data && (
              <tr>
                <td colSpan={cols.length} className="sub">
                  {t.loading}
                </td>
              </tr>
            )}
            {data?.rows.length === 0 && (
              <tr>
                <td colSpan={cols.length} className="sub">
                  {t.empty}
                </td>
              </tr>
            )}
            {data?.rows.map((r) => (
              <tr
                key={r.item_id}
                onClick={() => setPick(r.item_id)}
                className={pick === r.item_id ? "row-on" : ""}
                style={{ cursor: pc ? "pointer" : undefined }}
              >
                {cols.map((c) => (
                  <td key={c}>{cell(r, c)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {pc && (
        <div className="pc-sticky" style={{ maxHeight: "calc(100vh - 140px)", overflowY: "auto" }}>
          <PickPanel id={pick ?? data?.rows[0]?.item_id ?? null} />
        </div>
      )}
      </div>
      <div className="sub">{t.note}</div>
    </main>
  );
}

export default function ProItemsPage() {
  return (
    <Suspense>
      <ProItems />
    </Suspense>
  );
}
