"use client";

import Link from "next/link";
import type { SameBuilding as Sb } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.sameBuilding;

// 같은 건물(같은 지번)에서 나온 다른 경매(11/21) — 빌라 한 동 통째 · 같은 단지 다른 호
export function SameBuilding({ v }: { v?: Sb | null }) {
  if (!v || v.n === 0) return null;
  const rest = v.n - v.list.length;
  return (
    <div className="note mt-10">
      <b>{t.title(v.n, v.cases)}</b>
      <div className="mt-6">
        {v.list.map((x) => (
          <div key={x.item_id} className="mt-2">
            <Link prefetch={false} href={`/item/${x.item_id}`} className="link">
              {[x.no, x.unit, x.date.slice(5).replace("-", "/")].filter(Boolean).join(" · ")}
              {x.min_price_krw ? ` · 최저 ${won(x.min_price_krw)}` : ""}
            </Link>
          </div>
        ))}
      </div>
      {rest > 0 && <div className="sub fs-sm mt-2">{t.more(rest)}</div>}
    </div>
  );
}
