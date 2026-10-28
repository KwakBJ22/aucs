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
    <div className="note blue" style={{ marginTop: 10 }}>
      <b>{toCourt ? t.toCourt : t.toOnbid}</b>
      <div className="sub" style={{ fontSize: 13, margin: "2px 0 6px" }}>
        {t.sub}
      </div>
      {list.map((x) => (
        <Link
          key={x.item_id}
          href={`/item/${x.item_id}`}
          style={{ display: "block", fontSize: 14, padding: "4px 0" }}
        >
          {(x.source === "court" ? t.court : t.onbid)(x.no, x.date ?? "-")}
          {x.min_price_krw ? ` · 최저 ${won(x.min_price_krw)}` : ""} ›
        </Link>
      ))}
    </div>
  );
}
