"use client";

import { apiBaseUrl } from "@/lib/api/client";
import { supabase } from "@/lib/auth";

// 사용 기록(할 일 5): 화면 이동과 주요 동작만, 이름·이메일 없이. 성공 지표(처음 판단까지 시간·관심 등록률·주간 재방문)용.
// sendBeacon(text/plain)이라 화면을 기다리게 하지 않고, 사전 확인 요청도 없음. 실패해도 조용히 넘어감.
export type TrackKind =
  "view" | "start_done" | "item_view" | "watch_add" | "calc" | "bid_sheet" | "login" | "alert_on";

const KEY = "aucs_anon";

function anonId(): string {
  try {
    let v = localStorage.getItem(KEY);
    if (!v) {
      v = crypto.randomUUID();
      localStorage.setItem(KEY, v);
    }
    return v;
  } catch {
    return "no-storage-0000";
  }
}

let token: string | null = null;
// 로그인 기록은 메일 링크로 막 들어온 때만(세션을 다시 읽을 때도 SIGNED_IN 이 와서 매번 세지 않게)
const fromLink =
  typeof window !== "undefined" && /access_token=|[?&]code=/.test(window.location.href);
supabase?.auth.onAuthStateChange((e, s) => {
  token = s?.access_token ?? null;
  if (e === "SIGNED_IN" && fromLink && token) track("login");
});

export function track(kind: TrackKind, itemId?: string): void {
  if (typeof window === "undefined") return;
  try {
    const body = JSON.stringify({
      a: anonId(),
      k: kind,
      p: window.location.pathname,
      i: itemId,
      t: token ?? undefined,
    });
    const url = `${apiBaseUrl}/events`;
    if (!navigator.sendBeacon?.(url, new Blob([body], { type: "text/plain" })))
      void fetch(url, { method: "POST", body, keepalive: true, mode: "no-cors" });
  } catch {
    /* 기록 못 해도 화면은 그대로 */
  }
}
