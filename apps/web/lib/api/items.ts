import { getJson } from "./client";

export type Signal = { rule_id: string; level: string; title: string; status: string };
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
  computed_at: string | null;
};

export const fetchItem = (id: string) => getJson<ItemDetail>(`/items/${encodeURIComponent(id)}`);
