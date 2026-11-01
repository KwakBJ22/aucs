"use client";

import Link from "next/link";
import type { ItemDetail } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { complexName } from "@/lib/talk";

const t = copy.outcome;

// 끝난 물건 결과 한 줄(11/1): 상세 맨 위. 낙찰이면 금액·감정가 대비·옥스 예상 안/밖
export function OutcomeBand({ d }: { d: ItemDetail }) {
  const o = d.outcome;
  if (!o) return null;
  const date = o.date.slice(5).replace("-", "/");
  const sold = o.code === "sold" && o.winning_bid_krw;
  const main = sold
    ? t.sold(date, won(o.winning_bid_krw), o.rate)
    : o.code === "unknown"
      ? `${date} · ${t.unknown}`
      : t.other(date, o.text);
  const sub = sold
    ? o.expected
      ? o.within
        ? t.within
        : t.outside(won(o.expected[0]), won(o.expected[1]))
      : null
    : o.code === "failed"
      ? t.failedNext
      : null;
  return (
    <div className="bg-panel r-14 py-12 px-14 mt-10" role="status">
      <div className="fs-base fw-7">{main}</div>
      {sub && <div className="sub fs-sm mt-2">{sub}</div>}
      {o.closed && (
        <Link
          href={`/find?q=${encodeURIComponent(complexName(d))}`}
          className="fs-sm c-blue mt-6 d-inline-block"
        >
          {t.sameComplex}
        </Link>
      )}
    </div>
  );
}
