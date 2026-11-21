"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Delayed, SkLines } from "@/components/skeleton";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { Row } from "@/components/calc-box";
import { fetchItemTrades, type ItemTrades } from "@/lib/api/items";
import { won, wonShort } from "@/lib/format";
import { copy } from "@/lib/copy.ko";

const t = copy.itemTrades;
const FIRST = 20;

// 해마다 평균(선) · 최저~최고(옅은 띠) · 같은 면적 낙찰(빨간 점) — 실거래가 vs 낙찰가(11/21)
function Chart({ d }: { d: ItemTrades }) {
  const ys = d.years;
  if (ys.length < 2) return null;
  const W = 340, H = 150, L = 4, R = 4, T = 14, B = 18; // prettier-ignore
  const first = ys[0]!,
    last = ys[ys.length - 1]!;
  const y0 = first.y,
    y1 = last.y + 1;
  const sold = d.auctions.filter((a) => d.area && a.area && Math.abs(a.area - d.area) <= 3);
  const top = Math.max(...ys.map((x) => x.high), ...sold.map((a) => a.price), 1);
  const px = (yr: number) => L + ((yr - y0) / (y1 - y0)) * (W - L - R);
  const py = (v: number) => T + (1 - v / top) * (H - T - B);
  const mid = (x: { y: number }) => px(x.y + 0.5);
  const band =
    ys.map((x) => `${mid(x)},${py(x.high)}`).join(" ") +
    " " +
    [...ys]
      .reverse()
      .map((x) => `${mid(x)},${py(x.low)}`)
      .join(" ");
  return (
    <figure className="m-0 mt-8" style={{ maxWidth: 520 }} aria-label={t.chart}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        <polygon points={band} fill="var(--blue)" opacity={0.12} />
        <polyline
          points={ys.map((x) => `${mid(x)},${py(x.mid)}`).join(" ")}
          fill="none"
          stroke="var(--blue)"
          strokeWidth={2}
        />
        {sold.map((a) => {
          const dt = new Date(a.date);
          const yr = dt.getFullYear() + dt.getMonth() / 12;
          return yr < y0 ? null : (
            <circle key={a.date + a.price} cx={px(yr)} cy={py(a.price)} r={4} fill="var(--red)" />
          );
        })}
        <text x={L} y={10} fontSize={10} fill="var(--muted)">
          {wonShort(top)}
        </text>
        {[...new Set([first, ys[Math.floor(ys.length / 2)]!, last])].map((x) => (
          <text
            key={x.y}
            x={mid(x)}
            y={H - 4}
            fontSize={10}
            fill="var(--muted)"
            textAnchor="middle"
          >
            {String(x.y).slice(2)}
          </text>
        ))}
      </svg>
      <figcaption className="sub m-0 fs-xs">{t.chart}</figcaption>
    </figure>
  );
}

export default function TradesPage() {
  const id = decodeURIComponent(String(useParams().id));
  const [area, setArea] = useState<number | null>(null);
  const [d, setD] = useState<ItemTrades | null>(null);
  const [failed, setFailed] = useState(false);
  const [all, setAll] = useState(false);

  useEffect(() => {
    fetchItemTrades(id, area)
      .then(setD)
      .catch(() => setFailed(true));
  }, [id, area]);

  if (failed) return <LoadError onRetry={() => window.location.reload()} />;
  const rows = d ? (all ? d.recent : d.recent.slice(0, FIRST)) : [];
  return (
    <main className="page">
      <PageHeader title={t.title} back={`/item/${encodeURIComponent(id)}`} />
      {!d ? (
        <Delayed>
          <section className="section">
            <SkLines n={2} />
          </section>
          <section className="section">
            <SkLines n={8} />
          </section>
        </Delayed>
      ) : !d.years.length ? (
        <section className="section">
          <p className="sub m-0">{t.none}</p>
        </section>
      ) : (
        <>
          <section className="section">
            <div className="fs-base fw-6">{t.head(d.name, d.built)}</div>
            <div className="pills mt-8" role="group" aria-label={t.areaNote}>
              {d.areas.map((a) => (
                <button
                  key={a.area}
                  className={a.area === d.area ? "on" : ""}
                  onClick={() => {
                    setAll(false);
                    setArea(a.area);
                  }}
                >
                  {t.area(a.area)}
                </button>
              ))}
            </div>
            <Chart d={d} />
          </section>
          <section className="section">
            <h2>{t.years}</h2>
            {[...d.years].reverse().map((x) => (
              <Row
                key={x.y}
                label={t.yearRow(x.y, x.n)}
                value={
                  <>
                    <b>{won(x.mid)}</b>{" "}
                    <span className="sub m-0">
                      {x.kept > 1 ? t.range(wonShort(x.low), wonShort(x.high)) : ""}
                    </span>
                  </>
                }
              />
            ))}
          </section>
          {d.recent.length > 0 && (
            <section className="section">
              <h2>{t.recent}</h2>
              {rows.map((r, i) => (
                <Row
                  key={i}
                  label={[
                    r.date.slice(2).replaceAll("-", "."),
                    r.floor != null ? t.floor(r.floor) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  value={
                    r.kind === "sale" ? (
                      <>
                        <span className="sub m-0">{t.sale}</span> <b>{won(r.price)}</b>
                      </>
                    ) : r.rent ? (
                      <>
                        <span className="sub m-0">{t.wolse}</span> {won(r.deposit)} / {won(r.rent)}
                      </>
                    ) : (
                      <>
                        <span className="sub m-0">{t.jeonse}</span> {won(r.deposit)}
                      </>
                    )
                  }
                />
              ))}
              {!all && d.recent.length > FIRST && (
                <button className="link fs-sm mt-4" onClick={() => setAll(true)}>
                  {t.more(d.recent.length)}
                </button>
              )}
            </section>
          )}
          {d.auctions.length > 0 && (
            <section className="section">
              <h2>{t.auctions}</h2>
              {d.auctions.map((a) => (
                <Row
                  key={a.date + a.price}
                  label={[
                    a.date.slice(2).replaceAll("-", "."),
                    a.area ? t.area(Math.round(a.area)) : null,
                    a.unit,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  value={<b>{won(a.price)}</b>}
                />
              ))}
            </section>
          )}
          <p className="sub fs-xs">{t.basis(d.last)}</p>
        </>
      )}
    </main>
  );
}
