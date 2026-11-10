"use client";

import { useState } from "react";
import { useWatch } from "@/components/watch-context";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import Link from "next/link";

export function WsLink({ id }: { id: string }) {
  const { ids } = useWatch();
  if (!ids.has(id)) return null;
  return (
    <Link href={`/watch/${encodeURIComponent(id)}`} className="link">
      {copy.ws.open}
    </Link>
  );
}

// PC 물건 상세(PC-ITEM): 위 요약 띠 + 목차 14 · 본문 62 · 행동 칸 24. 다섯 질문을 모두 펼칩니다.
export function CompareAdd({ id }: { id: string }) {
  const { session } = useSession();
  const [msg, setMsg] = useState("");
  if (!session) return null;
  return (
    <button
      className="pc-act"
      onClick={() =>
        meApi
          .addCompare(session.access_token, id)
          .then(() => setMsg(copy.compare.added))
          .catch(() => setMsg(copy.compare.full(5)))
      }
    >
      {msg || copy.compare.add}
    </button>
  );
}
