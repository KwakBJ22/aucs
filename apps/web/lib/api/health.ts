import { getJson } from "./client";

export type HealthState = "checking" | "ok" | "fail";

type HealthBody = { ok: boolean };

// 응답을 화면 상태 세 가지로 바꿉니다.
export function toHealthState(body: HealthBody | null): HealthState {
  if (body === null) return "fail";
  return body.ok ? "ok" : "fail";
}

async function check(path: string): Promise<HealthState> {
  try {
    return toHealthState(await getJson<HealthBody>(path));
  } catch {
    return "fail";
  }
}

export const checkApi = () => check("/health");
export const checkDb = () => check("/health/db");
