"use client";

import { useEffect } from "react";
import { copy } from "@/lib/copy.ko";
import { reportError } from "@/lib/report-error";

// 화면 하나가 멈췄을 때: 기록을 남기고 「다시 해 보기」만 보여 줌(다른 탭·메뉴는 그대로)
export default function ScreenError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => reportError(error), [error]);
  return (
    <main className="page">
      <section className="section" role="alert">
        <b className="fs-base">{copy.states.crashTitle}</b>
        <p className="sub mt-4 mb-10 mx-0">{copy.states.crashSub}</p>
        <button className="chip gray b-0 mh-40" onClick={reset}>
          {copy.states.retry}
        </button>
      </section>
    </main>
  );
}
