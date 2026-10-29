"use client";

import { Row } from "@/components/calc-box";
import { won } from "@/lib/format";
import { useIsPc } from "@/lib/use-pc";
import { t } from "@/components/item/shared";

// 건축물대장(10/27): 사용승인·건물 모양·세대·승강기·주차, 이 층 용도(근생이면 빨강)
export type Bldg = {
  built: string | null;
  old: boolean;
  shape: string | null;
  extra: string | null;
  unit: string | null;
  villa: "confirmed" | "mixed" | "clear" | null;
};

export function BuildingRows({ g }: { g: Bldg }) {
  const c = t.bldg;
  const tone =
    g.villa === "confirmed" ? "var(--red)" : g.villa === "mixed" ? "var(--orange)" : undefined;
  return (
    <>
      {g.built && (
        <Row
          label={c.built}
          value={<span style={{ color: g.old ? "var(--orange)" : undefined }}>{g.built}</span>}
        />
      )}
      {g.shape && <Row label={c.shape} value={g.shape} />}
      {g.extra && <Row label="" value={g.extra} />}
      {g.unit && (
        <Row
          label={c.unit}
          value={
            <span style={{ color: tone }}>
              {g.unit}
              {g.villa === "confirmed"
                ? ` · ${c.villa}`
                : g.villa === "mixed"
                  ? ` · ${c.mixed}`
                  : ""}
            </span>
          }
        />
      )}
    </>
  );
}

// 같은 단지(10/27): 지난 낙찰 사례 · 실거래 추이 · 전월세. 휴대폰은 줄 몇 개, PC는 분기별 막대까지
export type Complex = {
  auctions: {
    date: string;
    price_krw: number;
    rate: number | null;
    failed: number | null;
    unit: string | null;
    case_no: string;
    court: string;
  }[];
  trend: {
    recent_krw: number | null;
    recent_n: number;
    prev_krw: number | null;
    change_pct: number | null;
    jeonse_krw: number | null;
    jeonse_n: number;
    wolse_deposit_krw: number | null;
    wolse_rent_krw: number | null;
    wolse_n: number;
    area_match: boolean;
  };
  quarters: { q: string; price_krw: number; n: number }[];
};

export function ComplexBlock({ cx }: { cx: Complex }) {
  const c = t.complex;
  const pc = useIsPc();
  const tr = cx.trend;
  const top = Math.max(...cx.quarters.map((x) => x.price_krw), 1);
  const low = Math.min(...cx.quarters.map((x) => x.price_krw));
  return (
    <div className="mt-10">
      {cx.auctions.length > 0 && (
        <>
          <div className="sub mt-8 mb-2 mx-0">{c.auctions(cx.auctions.length)}</div>
          {cx.auctions.slice(0, pc ? 8 : 2).map((a) => (
            <Row
              key={a.case_no + a.date}
              label={`${a.date.slice(2, 7).replace("-", ".")}${a.unit ? ` · ${a.unit}` : ""}`}
              value={
                <>
                  <b>{won(a.price_krw)}</b>{" "}
                  <span className="sub m-0">
                    {[a.rate != null ? c.rate(a.rate) : null, a.failed ? c.failed(a.failed) : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </>
              }
            />
          ))}
        </>
      )}
      {tr.recent_krw && (
        <Row
          label={c.recent(tr.recent_n)}
          value={
            <>
              <b>{won(tr.recent_krw)}</b>
              {tr.change_pct != null && (
                <span
                  className="sub m-0"
                  style={{ color: tr.change_pct >= 0 ? "var(--red)" : "var(--blue)" }}
                >
                  {" "}
                  {c.change(tr.change_pct)}
                </span>
              )}
            </>
          }
        />
      )}
      {(tr.jeonse_krw || tr.wolse_rent_krw) && (
        <Row
          label={c.lease}
          value={[
            tr.jeonse_krw ? c.jeonse(won(tr.jeonse_krw), tr.jeonse_n) : null,
            tr.wolse_rent_krw
              ? c.wolse(won(tr.wolse_deposit_krw), won(tr.wolse_rent_krw), tr.wolse_n)
              : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        />
      )}
      {pc && cx.quarters.length > 1 && (
        <div
          role="img"
          aria-label={c.chart}
          className="d-flex ai-end gap-6 mt-8"
          style={{ height: 64 }}
        >
          {cx.quarters.map((x) => (
            <div key={x.q} className="f-1 ta-center fs-xs">
              <div
                title={`${x.q} ${won(x.price_krw)} (${x.n}건)`}
                className="bg-blue-soft"
                style={{
                  height: 8 + (40 * (x.price_krw - low)) / Math.max(top - low, 1),
                  borderTop: "2px solid var(--blue)",
                }}
              />
              <span className="sub m-0 fs-xs">{x.q.replace("분기", "")}</span>
            </div>
          ))}
        </div>
      )}
      {!tr.area_match && <div className="sub mt-4 mb-0 mx-0 fs-xs">{c.allAreas}</div>}
    </div>
  );
}
