// PC 전문가 「전체 물건」 표
import { apiBaseUrl, getJson } from "./client";

export type ProFilter = {
  source?: "all" | "court" | "onbid";
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
  source: "court" | "onbid";
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
  const src = q.get("source");
  return {
    source: src === "court" || src === "onbid" ? src : undefined,
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

// 사건·문건 분석
export type CaseRow = {
  case_id: string;
  court: string;
  case_no: string;
  item_id: string;
  place: string;
  sale_date: string | null;
  d_day: number | null;
  flags: string[];
  last_date: string | null;
  late: number;
};
export type CaseEvent = {
  event_date: string | null;
  kind: string | null;
  category: string;
  importance: "high" | "mid" | "low";
  after_deadline: boolean;
  text_masked: string | null;
};
export type CaseDetail = {
  case_id: string;
  court: string;
  case_no: string;
  dept: string | null;
  claim_deadline: string | null;
  progress: string | null;
  items: {
    item_id: string;
    item_no: number;
    sale_date: string | null;
    d_day: number | null;
    usage_name: string | null;
    address: string | null;
    min_price_krw: number | null;
    appraisal_krw: number | null;
  }[];
  counts: [string, number][];
  events: CaseEvent[];
};
export const fetchCases = (category?: string, q?: string) => {
  const p = new URLSearchParams();
  if (category) p.set("category", category);
  if (q) p.set("q", q);
  return getJson<{ categories: string[]; cases: CaseRow[] }>(`/pro/cases?${p}`);
};
export const fetchCase = (id: string) =>
  getJson<CaseDetail>(`/pro/cases/${encodeURIComponent(id)}`);

// 낙찰 사례와 시장 분석
export type Stat = { n: number; p50: number };
export type Market = {
  by_court: (Stat & { court: string; court_code: string })[];
  by_failed: (Stat & { failed: number })[];
  by_month: (Stat & { month: string })[];
  by_usage: (Stat & { usage: string })[];
  misses: {
    sale_date: string;
    court: string;
    case_no: string;
    address: string | null;
    sale_rate: number;
    p25: number;
    p75: number;
    item_id: string | null;
  }[];
  cases: {
    sale_date: string;
    court: string;
    case_no: string;
    usage_name: string | null;
    address: string | null;
    building_area_m2: number | null;
    appraisal_krw: number | null;
    winning_bid_krw: number | null;
    sale_rate: number;
    failed_count: number | null;
    item_id: string | null;
  }[];
  scorecard: { n: number; inside: number; below: number; above: number };
};
export const fetchMarket = (f: {
  sido?: string;
  sigungu?: string;
  usage?: string[];
  months?: number;
}) => getJson<Market>(`/pro/market?${toQuery(f)}`);

// 공매 시장(전국 입찰 결과). p50 = 최저가 대비, p50_app = 감정가 대비
export type OnbidStat = Stat & { p50_app: number | null };
export type OnbidMarket = {
  basis: string;
  by_sido: (OnbidStat & { sido: string | null })[];
  by_bidders: (OnbidStat & { bidders: string })[];
  by_failed: (OnbidStat & { failed: number })[];
  by_month: (OnbidStat & { month: string })[];
  by_usage: (OnbidStat & { usage: string })[];
  cases: {
    sale_date: string;
    mng_no: string;
    kind_name: string | null;
    usage_name: string | null;
    title: string | null;
    building_m2: number | null;
    appraisal_krw: number | null;
    min_price_krw: number | null;
    win_krw: number | null;
    rate_min: number | null;
    rate_appraisal: number | null;
    bidders: number | null;
  }[];
};
export const fetchOnbidMarket = (f: {
  sido?: string;
  sigungu?: string;
  usage?: string[];
  months?: number;
}) => getJson<OnbidMarket>(`/pro/market?${toQuery({ ...f, source: "onbid" } as ProFilter)}`);
