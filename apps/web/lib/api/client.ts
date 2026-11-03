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

function remembered<T>(box: Map<string, Entry>, key: string, ttl: number, load: () => Promise<T>) {
  const hit = box.get(key);
  if (hit && Date.now() - hit.at < ttl) return hit.p as Promise<T>;
  const p = load().catch((e: unknown) => {
    if (box.get(key)?.p === p) box.delete(key); // 실패한 것은 기억하지 않음
    throw e;
  });
  box.set(key, { at: Date.now(), p });
  if (box.size > 200) box.delete(box.keys().next().value as string);
  return p;
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
  return remembered(mine, `${token.slice(-16)} ${path}`, ME_TTL, () =>
    fetchJson<T>(`${apiBaseUrl}${path}`, { headers: { Authorization: `Bearer ${token}` } }),
  );
}

export function clearMeCache(): void {
  mine.clear();
}
