"use client";

// 화면 이동 때 스크롤 한 곳(11/8, project-standard 3-9):
//  · 새 화면으로 가면 맨 위에서 시작(Next는 새 화면 머리가 이미 보이면 위로 안 올려 중간에서 시작했음)
//  · 주소에 #자리가 있으면 그 자리로(자료가 늦게 와도 그려진 뒤에)
//  · 뒤로·앞으로·새로고침은 보던 위치로(자료가 다 그려져 그만큼 길어진 뒤에)
// 브라우저 기본 기능을 덮지 않고 부르기만 함. 기다림은 숫자 대신 「화면이 바뀔 때」를 봄.
const KEY = "aucs_scroll"; // 탭이 살아 있는 동안만(sessionStorage) — 화면 주소별 세로 위치

const here = () => window.location.pathname + window.location.search;

function readAll(): Record<string, number> {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || "{}") as Record<string, number>;
  } catch {
    return {};
  }
}

function save(path: string, y: number) {
  try {
    const all = readAll();
    all[path] = Math.round(y);
    const keys = Object.keys(all);
    if (keys.length > 60) delete all[keys[0]!]; // 오래된 것부터 버림
    sessionStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    /* 저장 못 해도 화면은 그대로 */
  }
}

let stop: (() => void) | null = null; // 지금 기다리는 일(되살리기·#자리 찾기)

// 조건이 맞을 때까지 화면 변화를 지켜봄. 손님이 먼저 움직이면 그만둠.
function waitFor(test: () => boolean, then: () => void) {
  stop?.();
  if (test()) return then();
  const mo = new MutationObserver(check);
  const ro = new ResizeObserver(check);
  const quit = () => end();
  function check() {
    if (test()) {
      end();
      then();
    }
  }
  function end() {
    mo.disconnect();
    ro.disconnect();
    ["wheel", "touchstart", "keydown"].forEach((e) => window.removeEventListener(e, quit));
    if (stop === end) stop = null;
  }
  mo.observe(document.body, { childList: true, subtree: true });
  ro.observe(document.body);
  ["wheel", "touchstart", "keydown"].forEach((e) =>
    window.addEventListener(e, quit, { passive: true, once: true }),
  );
  stop = end;
}

let restoring = false;

function goHash(): boolean {
  const id = decodeURIComponent(window.location.hash.slice(1));
  if (!id) return false;
  waitFor(
    () => document.getElementById(id) != null,
    () => document.getElementById(id)?.scrollIntoView({ block: "start" }),
  );
  return true;
}

function restore(path: string) {
  const y = readAll()[path];
  if (!y) return;
  restoring = true;
  waitFor(
    () => document.documentElement.scrollHeight - window.innerHeight >= y,
    () => {
      window.scrollTo(0, y);
      restoring = false;
    },
  );
}

let back = false; // 이번 이동이 뒤로·앞으로인지
let lastPath = ""; // 마지막으로 맞춘 화면(경로만)

// 앱이 처음 열릴 때 한 번: 위치를 우리가 맞추겠다고 브라우저에 알리고, 위치를 적기 시작
export function startScrollMemory(): () => void {
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  let ticking = false;
  const onScroll = () => {
    if (ticking || restoring) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      if (!restoring) save(here(), window.scrollY);
    });
  };
  const onPop = () => {
    back = true;
    // 같은 화면에서 주소 뒤쪽(?…)만 바뀐 뒤로 가기는 화면 바뀜 알림이 없어 여기서 맞춤
    requestAnimationFrame(() => {
      if (back && window.location.pathname === lastPath) {
        back = false;
        if (!goHash()) restore(here());
      }
    });
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("popstate", onPop);
  lastPath = window.location.pathname;
  // 새로고침·다시 열기: 보던 자리로(#자리가 있으면 그쪽)
  if (!goHash()) restore(here());
  return () => {
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("popstate", onPop);
    stop?.();
  };
}

// 화면 주소가 바뀐 뒤 한 번
export function onRouteChange() {
  lastPath = window.location.pathname;
  stop?.();
  restoring = false;
  if (back) {
    back = false;
    if (!goHash()) restore(here());
    return;
  }
  if (!goHash()) window.scrollTo(0, 0);
}

// 지금 보는 탭을 한 번 더 누르면 맨 위로(앱들이 하는 대로)
export function toTop() {
  stop?.();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
