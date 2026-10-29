"use client";

import { useEffect } from "react";
import { copy } from "@/lib/copy.ko";
import { reportError } from "@/lib/report-error";

// 맨 바깥(레이아웃)까지 멈췄을 때 — 스타일이 없을 수 있어 글만 간단히
export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => reportError(error), [error]);
  return (
    <html lang="ko">
      <body style={{ fontFamily: "sans-serif", padding: 24 }}>
        <p>
          <b>{copy.states.crashTitle}</b>
        </p>
        <p>{copy.states.crashSub}</p>
        <button onClick={reset}>{copy.states.retry}</button>
      </body>
    </html>
  );
}
