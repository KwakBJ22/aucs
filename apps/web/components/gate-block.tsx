"use client";

import Link from "next/link";
import { copy } from "@/lib/copy.ko";

// 상세가 막혔을 때(11/17): 402 하루 무료 끝 → 이용권 · 429 너무 많이 엶. 401(로그인)은 화면 묶음(layout)이 먼저 막음.
export function GateBlock({ status }: { status: 402 | 429 }) {
  return (
    <section className="section ta-center py-32 px-18">
      <p className="sub mb-20 mx-0">{status === 402 ? copy.gate.paid : copy.gate.tooMany}</p>
      {status === 402 && (
        <Link href="/plans" className="btn primary">
          {copy.gate.plans}
        </Link>
      )}
    </section>
  );
}
