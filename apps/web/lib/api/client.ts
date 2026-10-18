// API 주소와 공통 호출. 화면은 이 파일을 통해서만 자료를 부릅니다.
// 같은 와이파이의 휴대폰으로 열면(주소가 192.168.x.x) API도 그 PC 주소로 부릅니다.
const envBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";
export const apiBaseUrl =
  typeof window !== "undefined" &&
  envBase.includes("localhost") &&
  window.location.hostname !== "localhost"
    ? envBase.replace("localhost", window.location.hostname)
    : envBase;

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}
