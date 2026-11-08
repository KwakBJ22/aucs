"use client";

// 홈 화면에 두기(앱 설치) 한 곳(11/8): 브라우저가 주는 「설치」 기회를 페이지가 열리자마자 잡아 두고
// 버튼(내 정보·홈)과 첫 관심 안내 창이 같이 씀. 서비스 워커는 모든 손님에게 등록해야
// 크롬·엣지·삼성 인터넷이 주소창에 설치 버튼을 스스로 띄움.
type PromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: PromptEvent | null = null;
const subs = new Set<() => void>();
const tell = () => subs.forEach((f) => f());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); // 우리 버튼에서 띄움(크롬 자체 안내 띠는 접음)
    deferred = e as PromptEvent;
    tell();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    tell();
  });
}

export function onInstallChange(f: () => void): () => void {
  subs.add(f);
  return () => subs.delete(f);
}

export function canPrompt(): boolean {
  return deferred != null;
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export type Platform = "ios" | "android" | "mac" | "pc";
export function platform(): Platform {
  const ua = navigator.userAgent;
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1))
    return "ios";
  if (/android/i.test(ua)) return "android";
  if (/macintosh/i.test(ua)) return "mac";
  return "pc";
}

// 설치 창을 띄움. 띄웠으면 true(손님이 고른 결과와 상관없이), 브라우저가 기회를 안 줬으면 false
export async function promptInstall(): Promise<boolean> {
  const e = deferred;
  if (!e) return false;
  await e.prompt();
  await e.userChoice.catch(() => null);
  deferred = null; // 한 번 쓰면 끝(브라우저가 다음 기회를 다시 줌)
  tell();
  return true;
}

export function registerSW(): void {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/sw.js").catch(() => {
    /* 못 해도 화면은 그대로 */
  });
}
