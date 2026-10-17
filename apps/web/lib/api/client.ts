// API 주소와 공통 호출. 화면은 이 파일을 통해서만 자료를 부릅니다.
export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}
