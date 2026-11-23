"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Delayed, SkLines } from "@/components/skeleton";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { Row } from "@/components/calc-box";
import { fetchItemTrades, type ItemTrades } from "@/lib/api/items";
import { won, wonShort } from "@/lib/format";
import { copy } from "@/lib/copy.ko";
import { useIsPc } from "@/lib/use-pc";

const t = copy.itemTrades;
const FIRST = 20;

// 해마다 평균(선) · 최저~최고(옅은 띠) · 같은 면적 낙찰(빨간 점) — 실거래가 vs 낙찰가(11/21)
// wide(PC, 11/22 디자인): 칸 폭 전체로 넓게 — 글자 크기가 그대로 보이게 그림 폭 자체를 키움
function Chart({ d, wide }: { d: ItemTrades; wide?: boolean }) {
  const ys = d.years;
  if (ys.length < 2) return null;
  const W = wide ? 1100 : 340, H = wide ? 260 : 150, L = 4, R = 4, T = wide ? 22 : 14, B = wide ? 26 : 18; // prettier-ignore
  const fs = wide ? 14 : 10;
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
    <figure className="m-0 mt-8 tr-chart" aria-label={t.chart}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        <polygon points={band} fill="var(--blue)" opacity={0.12} />
        <polyline
          points={ys.map((x) => `${mid(x)},${py(x.mid)}`).join(" ")}
          fill="none"
          stroke="var(--blue)"
          strokeWidth={wide ? 3 : 2}
        />
        {sold.map((a) => {
          const dt = new Date(a.date);
          const yr = dt.getFullYear() + dt.getMonth() / 12;
          return yr < y0 ? null : (
            <circle key={a.date + a.price} cx={px(yr)} cy={py(a.price)} r={4} fill="var(--red)" />
          );
        })}
        <text x={L} y={fs} fontSize={fs} fill="var(--muted)">
          {wonShort(top)}
        </text>
        {[...new Set([first, ys[Math.floor(ys.length / 2)]!, last])].map((x) => (
          <text
            key={x.y}
            x={mid(x)}
            y={H - 4}
            fontSize={fs}
            fill="var(--muted)"
            textAnchor="middle"
          >
            {x.y}
          </text>
        ))}
      </svg>
      <figcaption className="sub m-0 fs-xs">{t.chart}</figcaption>
    </figure>
  );
}

// 같은 동네 비슷한 집(11/21) — 이 건물 거래가 없을 때만, 참고값(입찰가 셈에 안 씀)
function Nearby({ d }: { d: ItemTrades }) {
  const nb = d.nearby;
  return (
    <>
      <section className="section">
        <h2>{t.nearTitle}</h2>
        <p className="sub m-0">{t.nearWhy}</p>
        {!nb ? (
          <p className="sub mt-8 mb-0">{t.nearNone}</p>
        ) : (
          <>
            <Row label={t.nearValue} value={<b>{won(nb.value)}</b>} />
            <div className="sub m-0 fs-xs">
              {t.nearBasis(nb.n, nb.lots, nb.low_m2, nb.high_m2, nb.built)}
            </div>
            <div className="note blue mt-8">{t.nearNote}</div>
          </>
        )}
      </section>
      {nb && nb.buildings.length > 0 && (
        <section className="section">
          {nb.buildings.map((x) => (
            <Row
              key={x.lot ?? x.name ?? x.last}
              label={t.nearRow(x.name, x.built, x.area)}
              value={
                <>
                  <b>{won(x.mid)}</b> <span className="sub m-0">{t.nearN(x.n, x.last)}</span>
                </>
              }
            />
          ))}
        </section>
      )}
      <p className="sub fs-xs">{t.nearBasisSrc}</p>
    </>
  );
}

export default function TradesPage() {
  const id = decodeURIComponent(String(useParams().id));
  const pc = useIsPc();
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
      {/* PC 는 제목 위에 「‹ 물건 상세」(11/22 디자인) */}
      {pc && (
        <Link href={`/item/${encodeURIComponent(id)}`} className="back-link">
          ‹ {t.backDetail}
        </Link>
      )}
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
        "nearby" in d ? (
          <Nearby d={d} />
        ) : (
          <section className="section">
            <p className="sub m-0">{t.none}</p>
          </section>
        )
      ) : (
        <>
          <section className="section">
            <div className={pc ? "fs-base fw-6" : "fs-lg fw-7"}>{t.head(d.name, d.built)}</div>
            <div className="pills mt-8 area-pick" role="group" aria-label={t.areaNote}>
              {d.areas.map((a) => (
                <button
                  key={a.area}
                  className={a.area === d.area ? "on" : ""}
                  onClick={() => {
                    setAll(false);
                    setArea(a.area);
                  }}
                >
                  {a.area === d.area ? "✓ " : ""}
                  {t.area(a.area)}
                </button>
              ))}
            </div>
            <Chart d={d} wide={pc} />
          </section>
          <div className="pc-grid g-2x2">
            <section className="section">
              <h2>{t.years}</h2>
              {pc && d.area && <p className="sub">{t.yearsSub(d.area)}</p>}
              {[...d.years].reverse().map((x) => (
                <Row
                  key={x.y}
                  label={t.yearRow(x.y, x.n)}
                  value={
                    <>
                      <b>{won(x.mid)}</b>{" "}
                      <span className="sub m-0">
                        {x.kept > 1 && x.low !== x.high
                          ? t.range(wonShort(x.low), wonShort(x.high))
                          : ""}
                      </span>
                    </>
                  }
                />
              ))}
            </section>
            {d.recent.length > 0 && (
              <section className="section">
                <h2>{t.recent}</h2>
                {pc && <p className="sub">{t.recentSub}</p>}
                {rows.map((r, i) => (
                  <Row
                    key={i}
                    hl={pc && r.kind === "sale"}
                    label={[
                      r.date.slice(2).replaceAll("-", "."),
                      r.floor != null ? t.floor(r.floor) : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                    value={
                      r.kind === "sale" ? (
                        <>
                          <span className={pc ? "c-blue-text fs-sm" : "sub m-0"}>{t.sale}</span>{" "}
                          <b>{won(r.price)}</b>
                        </>
                      ) : r.rent ? (
                        <>
                          <span className="sub m-0">{t.wolse}</span> {won(r.deposit)} /{" "}
                          {won(r.rent)}
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
          </div>
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
