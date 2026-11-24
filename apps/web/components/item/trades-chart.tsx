"use client";

import { useEffect, useState } from "react";
import { fetchItemTrades, type ItemTrades } from "@/lib/api/items";
import { wonShort } from "@/lib/format";
import { copy } from "@/lib/copy.ko";

const t = copy.itemTrades;

// 해마다 평균(선) · 최저~최고(옅은 띠) · 같은 면적 낙찰(빨간 점) — 실거래가 vs 낙찰가(11/21)
// wide(PC, 11/22 디자인): 칸 폭 전체로 넓게 — 글자 크기가 그대로 보이게 그림 폭 자체를 키움
export function TradesChart({ d, wide }: { d: ItemTrades; wide?: boolean }) {
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

// 상세 「얼마짜리인가」에 실거래 그래프(11/24 대표님 — 한눈에 거래 금액, 전체는 새 창). 못 받으면 아무것도 안 그림
export function WorthTradesChart({ id }: { id: string }) {
  const [d, setD] = useState<ItemTrades | null>(null);
  useEffect(() => {
    fetchItemTrades(id)
      .then(setD)
      .catch(() => setD(null));
  }, [id]);
  return d && d.years.length > 1 ? <TradesChart d={d} /> : null;
}
