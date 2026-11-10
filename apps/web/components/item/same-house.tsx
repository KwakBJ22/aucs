"use client";

import Link from "next/link";
import type { SameHouse as Twin } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.sameHouse;

// 같은 집이 경매·공매에 함께 나온 경우 한 줄(동·호수까지 맞을 때만 이음)
export function SameHouse({ list }: { list?: Twin[] }) {
  if (!list || list.length === 0) return null;
  const toCourt = list[0]?.source === "court";
  return (
    <div className="note blue mt-10">
      <b>{toCourt ? t.toCourt : t.toOnbid}</b>
      <div className="sub fs-sm mt-2 mb-6 mx-0">{t.sub}</div>
      {list.map((x) => (
        <Link key={x.item_id} href={`/item/${x.item_id}`} className="link">
          {(x.source === "court" ? t.court : t.onbid)(x.no, x.date ?? "-")}
          {x.min_price_krw ? ` · 최저 ${won(x.min_price_krw)}` : ""}
        </Link>
      ))}
    </div>
  );
}
