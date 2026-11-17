// 휴대폰 「기본 / 전문가」 보기(11/17 대표님): 머리의 「전문가로」를 누르면 아래 탭 다섯 칸이 전문가 메뉴로 바뀜.
// 고른 것은 이 기기에 기억(다시 열어도 그대로). 전문가 화면(/pro · /compare)에 들어오면 저절로 전문가,
// 기본 탭 화면(홈 · 찾기 · 관심 · 내 경매 · 포인트)에 들어오면 저절로 기본 — 탭과 있는 화면이 어긋나지 않게.
import { useSyncExternalStore } from "react";

export type Mode = "basic" | "pro";
const KEY = "aucs_mode";
const EVENT = "aucs:mode";

function read(): Mode {
  try {
    return localStorage.getItem(KEY) === "pro" ? "pro" : "basic";
  } catch {
    return "basic";
  }
}

export function setMode(m: Mode): void {
  if (read() === m) return;
  try {
    localStorage.setItem(KEY, m);
  } catch {
    /* 기억 못 하는 브라우저 — 이번 화면에서만 */
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(cb: () => void): () => void {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useMode(): Mode {
  return useSyncExternalStore(subscribe, read, () => "basic");
}
