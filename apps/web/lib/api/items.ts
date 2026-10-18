import { getJson } from "./client";

export type Signal = {
  rule_id: string;
  level: string;
  title: string;
  status: string;
  ftype?: string | null;
};
export type SchedRow = {
  key: string;
  label: string;
  todo: string;
  basis: string;
  start: string;
  end: string;
  text: string;
  short: string;
  status: string;
  deadline: boolean;
};
export type Schedule = {
  rows: SchedRow[];
  summary: { pay: string; move_out: [string, string]; forced: [string, string]; line: string };
  pay_estimated: boolean;
};
export type BidCheck = {
  level: "ok" | "stop" | "block";
  message: string;
  ratio: number;
  korean: string;
  deposit_krw: number;
  resale: boolean;
  tips: string[];
};
export type ItemCard = {
  item_id: string;
  court: string;
  case_no: string;
  sale_date: string | null;
  d_day: number | null;
  usage: string | null;
  place: string;
  building: string | null;
  area_m2: number | null;
  appraisal_krw: number | null;
  min_price_krw: number | null;
  min_rate: number | null;
  deposit_krw: number | null;
  failed_count: number | null;
  below_appraisal_krw: number;
  lat: number | null;
  lon: number | null;
  top_signal: Signal | null;
  unknown_count: number;
  data_status: Record<string, string>;
};
export type ItemList = { total: number; items: ItemCard[] };
export type RegionRow = { sido: string; sigungu: string; items: number };

export function fetchItems(opts: {
  sigungu?: string[];
  maxCash?: number | null;
  sort?: "deadline" | "rate";
  limit?: number;
}): Promise<ItemList> {
  const q = new URLSearchParams();
  (opts.sigungu ?? []).forEach((s) => q.append("sigungu", s));
  if (opts.maxCash) q.set("max_cash", String(opts.maxCash));
  if (opts.sort) q.set("sort", opts.sort);
  if (opts.limit) q.set("limit", String(opts.limit));
  return getJson<ItemList>(`/items?${q.toString()}`);
}

export const fetchRegions = () => getJson<RegionRow[]>("/regions");

export type Question = {
  key: "buy" | "hold" | "worth" | "cost" | "check";
  title: string;
  answer: string;
  tone: "green" | "gray" | "orange" | "red" | "blue";
  body: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
};
export type ItemDetail = ItemCard & {
  verdict: string;
  fatal: string | null;
  address: string | null;
  sale_place: string | null;
  dept_name: string | null;
  next_round: { min_price_krw: number | null; reduction_pct: number | null; verified: boolean };
  rounds: { sale_date: string; min_price_krw: number | null; result: string }[];
  tags: { label: string; ok: boolean }[];
  questions: Question[];
  failure_types: { code: string; title: string }[];
  schedule: Schedule;
  computed_at: string | null;
};

export const fetchItem = (id: string) => getJson<ItemDetail>(`/items/${encodeURIComponent(id)}`);

export const fetchBidCheck = (id: string, bid: number) =>
  getJson<BidCheck>(`/items/${encodeURIComponent(id)}/bid-check?bid=${bid}`);

export type CashBreakdown = {
  bid_krw: number;
  deposit_krw: number;
  loan_krw: number;
  loan: { pct: number; cap_krw: number | null; who: string; note: string | null };
  tax: { tax_krw: number; rate: number; total_pct: number; heavy: boolean };
  registration_krw: number;
  assumed_krw: number;
  cash_krw: number;
  total_krw: number;
};
export type Calc = {
  cls: "regulated" | "metro" | "other";
  cases: { key: string; bid_krw: number; rate: number; chance: string; cash_krw: number }[];
  selected: CashBreakdown;
  cap_krw: number | null;
  slider: { min: number; max: number; step: number };
  resale: boolean;
};
export function fetchCalc(
  id: string,
  o: { bid?: number | null; homes: number; first: boolean; loan?: number | null },
): Promise<Calc> {
  const q = new URLSearchParams({ homes: String(o.homes), first: String(o.first) });
  if (o.bid) q.set("bid", String(o.bid));
  if (o.loan != null) q.set("loan", String(o.loan));
  return getJson<Calc>(`/items/${encodeURIComponent(id)}/calc?${q.toString()}`);
}
