"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchCalc, type Calc } from "@/lib/api/items";
import { won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";
import { t } from "@/components/item/shared";

// 손해 안 보는 선(11/20 대표님 「진행」): 지난 낙찰가보다 먼저 「나는 얼마까지 써도 되나」를 맨 앞에.
// 추정 시세 − 세금·등기 − 명도·수리 − 떠안는 돈. 셈은 계산 상자와 같은 API(cap_krw) 하나.
// 집 수는 내 조건(이 기기)에서, 모르면 「집 없음」으로 셈하고 그렇다고 적음.
export function CapLine({ id, minPrice }: { id: string; minPrice: number | null }) {
  const c = t.cap;
  const [d, setD] = useState<Calc | null>(null);
  const [homes, setHomes] = useState(0);
  useEffect(() => {
    const p = loadProfile();
    const h = p?.homes ?? 0;
    setHomes(h);
    fetchCalc(id, {
      homes: h,
      first: Boolean(p?.firstTime),
      selling: h === 1 && Boolean(p?.selling),
    })
      .then(setD)
      .catch(() => setD(null));
  }, [id]);
  if (!d) return null;
  const calcHref = `/item/${encodeURIComponent(id)}/calc`;
  // 떠안는 돈을 모르면 선을 긋지 않음(계산 상자와 같은 까닭)
  if (d.cap_krw == null)
    return d.assume?.risk ? (
      <p className="sub fs-sm mt-10 mb-0">
        {c.assumeUnknown}{" "}
        <Link href={calcHref} className="link in">
          {c.toCalc}
        </Link>
      </p>
    ) : null;
  const p = d.cap_parts;
  const under = minPrice != null && d.cap_krw < minPrice;
  return (
    <div className={`cap-box${under ? " under" : ""}`}>
      <div className="sub m-0 fs-sm">{c.title}</div>
      <div className={`cap-v ${under ? "c-red" : ""}`}>{under ? c.none : won(d.cap_krw)}</div>
      {p && (
        <div className="sub m-0 fs-xs mt-4">
          {c.parts(
            won(p.market_krw),
            won(p.tax_krw),
            won(p.fix_krw),
            p.assume_krw ? won(p.assume_krw) : null,
          )}
        </div>
      )}
      <div className="sub m-0 fs-xs mt-2">
        {c.basis(homes)}{" "}
        <Link href={calcHref} className="link in fs-xs">
          {c.toCalc}
        </Link>
      </div>
    </div>
  );
}
