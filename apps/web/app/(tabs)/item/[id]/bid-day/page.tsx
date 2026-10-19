"use client";

import { useParams } from "next/navigation";
import { BidDaySheet } from "@/components/bid-day-sheet";
import { PageHeader } from "@/components/layout/page-header";
import { copy } from "@/lib/copy.ko";

// 입찰일 아침(BID-02) 화면: 휴대폰·PC 모두 한 장(가운데)
export default function BidDayPage() {
  const id = decodeURIComponent(String(useParams().id));
  return (
    <main className="page narrow">
      <PageHeader title={copy.bidDay.title} back={`/item/${encodeURIComponent(id)}`} />
      <BidDaySheet id={id} />
    </main>
  );
}
