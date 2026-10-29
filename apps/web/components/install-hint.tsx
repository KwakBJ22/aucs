"use client";

import { useEffect, useState } from "react";
import { copy } from "@/lib/copy.ko";

const t = copy.install;
const KEY = "aucs_install_hint";

type PromptEvent = Event & { prompt: () => Promise<void> };
let deferred: PromptEvent | null = null; // 안드로이드 크롬이 주는 「설치」 기회(한 번 잡아 둠)
if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e as PromptEvent;
  });
}

export function shouldShowInstallHint(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia("(display-mode: standalone)").matches) return false; // 이미 홈 화면에서 엶
  if (window.innerWidth >= 1024) return false; // PC는 안내하지 않음
  try {
    return !localStorage.getItem(KEY);
  } catch {
    return false;
  }
}

// 처음 관심 담을 때 한 번: 홈 화면에 두면 알림을 바로 받아요(아래에서 올라오는 창)
export function InstallHint({ onClose }: { onClose: () => void }) {
  const [ios, setIos] = useState(false);
  useEffect(() => {
    setIos(/iphone|ipad|ipod/i.test(navigator.userAgent));
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* 저장 못 해도 계속 */
    }
  }, []);
  const install = () => {
    if (deferred) void deferred.prompt().finally(onClose);
    else onClose();
  };
  return (
    <div
      onClick={onClose}
      className="pos-fixed"
      style={{ inset: 0, zIndex: 60, background: "rgba(0,0,0,0.35)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t.title}
        onClick={(e) => e.stopPropagation()}
        className="sheet pos-absolute"
        style={{ left: 0, right: 0, bottom: 0, maxWidth: 560, margin: "0 auto" }}
      >
        <div className="sheet-handle" />
        <div className="fs-lg fw-7">{t.title}</div>
        <p className="sub fs-md mt-6">{t.why}</p>
        {ios || !deferred ? (
          <div className="bg-panel r-14 p-12 mt-12 fs-md lh-16">{ios ? t.ios : t.other}</div>
        ) : null}
        <div className="btn-pair mt-16">
          <button className="btn secondary" onClick={onClose}>
            {t.later}
          </button>
          {!ios && deferred ? (
            <button className="btn primary" onClick={install}>
              {t.add}
            </button>
          ) : (
            <button className="btn primary" onClick={onClose}>
              {t.ok}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
