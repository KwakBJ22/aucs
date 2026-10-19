// PC 전문가 「전체 물건」 표
import { apiBaseUrl, getJson } from "./client";

export type ProFilter = {
  sido?: string;
  sigungu?: string;
  usage?: string[];
  exclude?: string[];
  failed_min?: number;
  failed_max?: number;
  app_min?: number;
  app_max?: number;
  rate_max?: number;
  days_max?: number;
  q?: string;
  sort?: string;
  page?: number;
};
export type ProRow = {
  item_id: string;
  court: string;
  case_no: string;
  item_no: number;
  usage: string | null;
  address: string | null;
  area_m2: number | null;
  appraisal_krw: number | null;
  min_price_krw: number | null;
  min_rate: number | null;
  failed_count: number | null;
  sale_date: string | null;
  d_day: number | null;
  market_krw: number | null;
  signal: string | null;
  fatal: boolean;
};
export type ProResult = {
  rows: ProRow[];
  summary: {
    n: number;
    app_sum: number;
    app_avg: number;
    app_max: number;
    min_sum: number;
    all: number;
  };
  page: number;
  limit: number;
};

// 조건 ↔ 주소창(조건 주소 저장). 금액은 화면에서 억 단위로 받고 API에는 원으로.
export function toQuery(f: ProFilter): URLSearchParams {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v == null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => q.append(k, String(x)));
    else q.set(k, String(v));
  }
  return q;
}
export function fromQuery(q: URLSearchParams): ProFilter {
  const n = (k: string) => (q.get(k) != null && q.get(k) !== "" ? Number(q.get(k)) : undefined);
  return {
    sido: q.get("sido") ?? undefined,
    sigungu: q.get("sigungu") ?? undefined,
    usage: q.getAll("usage"),
    exclude: q.getAll("exclude"),
    failed_min: n("failed_min"),
    failed_max: n("failed_max"),
    app_min: n("app_min"),
    app_max: n("app_max"),
    rate_max: n("rate_max"),
    days_max: n("days_max"),
    q: q.get("q") ?? undefined,
    sort: q.get("sort") ?? undefined,
    page: n("page"),
  };
}
const EOK = 100_000_000;
function apiQuery(f: ProFilter): URLSearchParams {
  const q = toQuery({
    ...f,
    app_min: f.app_min != null ? f.app_min * EOK : undefined,
    app_max: f.app_max != null ? f.app_max * EOK : undefined,
  });
  return q;
}
export const fetchPro = (f: ProFilter) => getJson<ProResult>(`/pro/items?${apiQuery(f)}`);
export const proCsvUrl = (f: ProFilter) => `${apiBaseUrl}/pro/items?${apiQuery(f)}&fmt=csv`;
