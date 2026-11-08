// API 주소와 공통 호출. 화면은 이 파일을 통해서만 자료를 부릅니다.
// 같은 와이파이의 휴대폰으로 열면(주소가 192.168.x.x) API도 그 PC 주소로 부릅니다.
const envBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";
export const apiBaseUrl =
  typeof window !== "undefined" &&
  envBase.includes("localhost") &&
  window.location.hostname !== "localhost"
    ? envBase.replace("localhost", window.location.hostname)
    : envBase;

// 10/27 속도 개선: 같은 자료를 여러 부품이 동시에 부르면 한 번만 보내고(진행 중인 요청을 같이 씀),
// 받은 것은 잠깐 기억해 뒤로 가기·탭 오가기 때 바로 보여 줌.
// 공개 자료는 1분, 내 자료는 30초. 내 자료를 바꾸는 요청(저장·삭제)이 있으면 내 자료 기억은 모두 비움.
type Entry = { at: number; p: Promise<unknown> };
const pub = new Map<string, Entry>();
const mine = new Map<string, Entry>();
const PUB_TTL = 60_000;
const ME_TTL = 30_000;

// 11/8 다시 여는 화면은 지난번 받은 것을 먼저(project-standard 3-5): 받은 답을 이 기기에 하루 적어 두고,
// 다시 열 때(새로고침·앱 다시 열기 포함) 그것을 바로 돌려준 뒤 뒤에서 새로 받음. 새 답이 다르면
// FRESH_EVENT 를 알려 화면이 조용히 다시 그림(useFresh). 내 자료는 계정마다 따로, 로그아웃하면 지움.
export const FRESH_EVENT = "aucs:fresh";
const DISK = "aucs_api:";
const DISK_AGE = 24 * 3600_000;
const DISK_MAX = 300_000; // 글자 수 — 큰 답(전체 목록 등)은 적지 않음

function diskGet(key: string): { at: number; v: unknown } | null {
  try {
    const s = localStorage.getItem(DISK + key);
    if (!s) return null;
    const x = JSON.parse(s) as { at: number; v: unknown };
    return Date.now() - x.at < DISK_AGE ? x : null;
  } catch {
    return null;
  }
}

function diskPut(key: string, v: unknown): string | null {
  try {
    const s = JSON.stringify(v);
    if (s.length > DISK_MAX) return s;
    localStorage.setItem(DISK + key, JSON.stringify({ at: Date.now(), v }));
    return s;
  } catch {
    return null; // 자리가 없거나 막힌 브라우저 — 기억 없이 계속
  }
}

function diskClear(prefix: string) {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k?.startsWith(DISK + prefix)) localStorage.removeItem(k);
    }
  } catch {
    /* 그대로 */
  }
}

let freshQueued = false;
function tellFresh() {
  if (freshQueued) return; // 여러 답이 한꺼번에 와도 한 번만 다시 그림
  freshQueued = true;
  requestAnimationFrame(() => {
    freshQueued = false;
    window.dispatchEvent(new Event(FRESH_EVENT));
  });
}

function remembered<T>(box: Map<string, Entry>, key: string, ttl: number, load: () => Promise<T>) {
  const hit = box.get(key);
  if (hit && Date.now() - hit.at < ttl) return hit.p as Promise<T>;
  // 지난번 것: 이 화면에서 받아 둔 것(시간 지남) → 없으면 기기에 적어 둔 것
  const prev = typeof window === "undefined" ? null : diskGet(key);
  const stale = hit ? hit.p : prev ? Promise.resolve(prev.v) : null;
  const p = load()
    .then((v) => {
      const s = diskPut(key, v);
      if (stale && (!prev || s === null || s !== JSON.stringify(prev.v))) tellFresh();
      return v;
    })
    .catch((e: unknown) => {
      if (box.get(key)?.p === p) box.delete(key); // 실패한 것은 기억하지 않음
      throw e;
    });
  if (stale) {
    // 지난번 것을 먼저 돌려주고, 새 답은 뒤에서 받아 기억을 바꿈
    box.set(key, { at: Date.now(), p: stale });
    p.then((v) => box.set(key, { at: Date.now(), p: Promise.resolve(v) })).catch(() => {});
    return stale as Promise<T>;
  }
  box.set(key, { at: Date.now(), p });
  if (box.size > 200) box.delete(box.keys().next().value as string);
  return p;
}

// 토큰은 한 시간마다 바뀌어서 계정 번호(sub)로 나눔
function account(token: string): string {
  try {
    const b = token.split(".")[1] ?? "";
    return (
      (JSON.parse(atob(b.replace(/-/g, "+").replace(/_/g, "/"))) as { sub?: string }).sub ?? ""
    );
  } catch {
    return token.slice(-16);
  }
}

/** 서버가 답한 오류(404 등). 연결이 안 된 것과 「없는 물건」을 화면에서 나눠 보여 주려고 씀. */
export class ApiError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`);
  }
}
export const isNotFound = (e: unknown) => e instanceof ApiError && e.status === 404;

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) throw new ApiError(res.status);
  return (await res.json()) as T;
}

/** 공개 자료(GET). ttl: 기억하는 시간(기본 1분, 지역 목록처럼 잘 안 바뀌는 것은 길게). */
export function getJson<T>(path: string, ttl = PUB_TTL): Promise<T> {
  return remembered(pub, path, ttl, () => fetchJson<T>(`${apiBaseUrl}${path}`));
}

/** 로그인한 사람의 자료(GET). 토큰마다 따로 기억. */
export function getMine<T>(token: string, path: string): Promise<T> {
  return remembered(mine, `me:${account(token)} ${path}`, ME_TTL, () =>
    fetchJson<T>(`${apiBaseUrl}${path}`, { headers: { Authorization: `Bearer ${token}` } }),
  );
}

/** 내 자료 기억 비우기(저장·삭제·로그아웃 뒤) — 기기에 적은 것까지. 지운 것이 잠깐 다시 보이지 않게. */
export function clearMeCache(): void {
  mine.clear();
  diskClear("me:");
}

/** 공개 요청(POST) — 답을 기다리지 않고 보내기만(서류 받기 줄 세우기 등, 11/4). 실패해도 화면은 그대로. */
export function postQuiet(path: string): void {
  fetch(`${apiBaseUrl}${path}`, { method: "POST" }).catch(() => {});
}
