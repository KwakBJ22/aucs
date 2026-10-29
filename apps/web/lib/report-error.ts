"use client";

import { apiBaseUrl } from "@/lib/api/client";

// 오류 기록(출시 전 꼭, 10/29): 화면에서 난 오류를 우리 API(/errors)로. 관리자 「오류」에서 묶어 봄.
// 같은 내용은 한 화면에서 한 번만, 개발 중 화면 고침(HMR) 소음은 뺌. 실패해도 조용히 넘어감.
const sent = new Set<string>();

function anonId(): string {
  try {
    return localStorage.getItem("aucs_anon") ?? "no-storage-0000";
  } catch {
    return "no-storage-0000";
  }
}

export function reportError(err: unknown): void {
  if (typeof window === "undefined") return;
  try {
    const e = err instanceof Error ? err : new Error(String(err));
    const m = `${e.name}: ${e.message}`.slice(0, 500);
    if (sent.has(m) || /ResizeObserver loop|Loading chunk|hot-update|NEXT_REDIRECT/.test(m)) return;
    sent.add(m);
    const body = JSON.stringify({
      a: anonId(),
      m,
      s: (e.stack ?? "").slice(0, 4000),
      p: window.location.pathname,
    });
    const url = `${apiBaseUrl}/errors`;
    if (!navigator.sendBeacon?.(url, new Blob([body], { type: "text/plain" })))
      void fetch(url, { method: "POST", body, keepalive: true, mode: "no-cors" });
  } catch {
    /* 기록 못 해도 화면은 그대로 */
  }
}

// 잡지 못한 오류·약속(Promise) 실패를 한 번에 받음 — Providers 에서 한 번 부름
export function listenErrors(): () => void {
  const onError = (ev: ErrorEvent) => reportError(ev.error ?? ev.message);
  const onReject = (ev: PromiseRejectionEvent) => reportError(ev.reason);
  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onReject);
  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onReject);
  };
}
