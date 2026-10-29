"use client";

import type { Interest } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";

// 관심도 한 줄(경쟁 신호로만). 적게 모였으면 서버가 안 보내서 줄도 없음
export function InterestLine({ v }: { v?: Interest | null }) {
  if (!v) return null;
  return <div className="sub fs-sm mt-6">{copy.interest.line(v.viewers_7d, v.watchers)}</div>;
}
