// 아카데미 과제 확인(11/18 대표님): 과제 버튼을 누르면 「기다리는 과제」만 적어 두고, 그 화면에서 실제로 해 보면
// 그때 「해 봤어요」로 셈(예전엔 버튼만 눌러도 셌음). 교안(academy.ko.ts)을 읽지 않는 작은 파일 — 모든 화면이 부름.
// 셈한 것은 기기 진도(aucs_academy)에 「task:수업」으로 적고, 아카데미 화면을 열 때 계정 진도와 합쳐짐(syncProgress).
const DONE = "aucs_academy";
const WAIT = "aucs_ac_wait";
const WAIT_DAYS = 7;

// 해 본 것: 사용 기록(track)의 종류 + 아카데미만 쓰는 몇 가지
export type Hit =
  | "view"
  | "item_view"
  | "calc"
  | "watch_add"
  | "alert"
  | "safe"
  | "mock"
  | "registry";

// need 꼴: "calc" 처럼 종류 하나, 또는 "view:^/me" 처럼 그 주소를 연 것(정규식)
export function waitTask(lesson: string, need: string): void {
  try {
    localStorage.setItem(WAIT, JSON.stringify({ lesson, need, at: Date.now() }));
  } catch {
    /* 저장이 막힌 브라우저 — 셈하지 못함 */
  }
}

export function taskDone(lesson: string): boolean {
  try {
    const v = JSON.parse(localStorage.getItem(DONE) ?? "[]") as unknown;
    return Array.isArray(v) && v.includes(`task:${lesson}`);
  } catch {
    return false;
  }
}

export function academyHit(kind: Hit, path?: string): void {
  if (typeof window === "undefined") return;
  try {
    const w = JSON.parse(localStorage.getItem(WAIT) ?? "null") as {
      lesson: string;
      need: string;
      at: number;
    } | null;
    if (!w || Date.now() - w.at > WAIT_DAYS * 86_400_000) return;
    const [k, re] = w.need.split(/:(.*)/s);
    if (k !== kind) return;
    if (re && !new RegExp(re).test(path ?? window.location.pathname)) return;
    const v = JSON.parse(localStorage.getItem(DONE) ?? "[]") as unknown;
    const list = Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
    const key = `task:${w.lesson}`;
    if (!list.includes(key)) localStorage.setItem(DONE, JSON.stringify([...list, key]));
    localStorage.removeItem(WAIT);
  } catch {
    /* 못 읽어도 화면은 그대로 */
  }
}
