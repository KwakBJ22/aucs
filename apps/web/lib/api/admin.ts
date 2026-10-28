import { apiBaseUrl } from "./client";

export type Job = {
  job_id: string;
  name_ko: string;
  started_at: string;
  status: string;
  item_count: number | null;
  message: string | null;
};
export type AdminStatus = {
  jobs: Job[];
  counts: { db_bytes: number; items_upcoming: number; sale_results: number; trades: number };
  db_limit_bytes: number;
  metrics?: {
    devices: number;
    started: number;
    viewed: number;
    watched: number;
    calc: number;
    first_item_sec: number | null;
    cohort: number;
    returned: number;
  };
};
export type Flag = { flag_key: string; enabled: boolean; note: string | null };
export type Review = {
  fields: { field_id: number; case_id: string; field: string; raw_text: string | null }[];
  signals: { item_id: string; title: string; sale_date: string }[];
  reports?: { report_id: number; item_id: string; section: string; note: string; at: string }[];
};
export type RuleRow = {
  rule_key: string;
  valid_from: string;
  valid_to: string | null;
  basis: string;
};

// 관리자 주소 호출. 열쇠가 틀리면 "denied" 오류.
async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBaseUrl}/admin${path}`, {
    ...init,
    headers: { "X-Admin-Token": token, "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (res.status === 403) throw new Error("denied");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const adminApi = {
  status: (t: string) => call<AdminStatus>(t, "/status"),
  review: (t: string) => call<Review>(t, "/review"),
  flags: (t: string) => call<Flag[]>(t, "/flags"),
  rules: (t: string) => call<RuleRow[]>(t, "/rule-tables"),
  closeReport: (t: string, id: number, status: "fixed" | "rejected") =>
    call<{ ok: boolean }>(t, `/reports/${id}`, { method: "PUT", body: JSON.stringify({ status }) }),
  setFlag: (t: string, key: string, enabled: boolean) =>
    call<Flag>(t, `/flags/${key}`, { method: "PUT", body: JSON.stringify({ enabled }) }),
};

export function formatBytes(n: number): string {
  return `${Math.round(n / 1024 / 1024)}MB`;
}
