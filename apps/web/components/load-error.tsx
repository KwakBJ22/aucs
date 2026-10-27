"use client";

import { copy } from "@/lib/copy.ko";

// 화면 상태 「오류」(STATES): 자료를 못 받았을 때 빈 목록처럼 보이지 않게 — 무엇이 안 됐는지 + 다시 시도.
export function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <section className="section" role="alert">
      <b style={{ fontSize: 15 }}>{copy.states.errorTitle}</b>
      <p className="sub" style={{ margin: "4px 0 10px" }}>
        {copy.states.errorSub}
      </p>
      <button className="chip gray" style={{ border: 0, minHeight: 40 }} onClick={onRetry}>
        {copy.states.retry}
      </button>
    </section>
  );
}
