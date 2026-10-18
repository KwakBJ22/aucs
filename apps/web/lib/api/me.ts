import { apiBaseUrl } from "./client";
import type { ItemCard, Schedule } from "./items";

export type WatchCard = ItemCard & { step: string };
export type SavedSearch = {
  search_id: number;
  name: string;
  filters: Record<string, unknown>;
  delivery: string;
};
export type Noti = {
  noti_id: number;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
};

export type Bid = {
  bid_id: number;
  item_id: string;
  sale_date: string;
  outcome: string;
  my_bid_krw: number | null;
  winning_bid_krw: number | null;
  second_bid_krw: number | null;
  bidder_count: number | null;
  pay_date: string | null;
  place: string | null;
  court_code: string | null;
  case_no: string | null;
  schedule?: Schedule;
};
export type BidTodo = { item_id: string; sale_date: string; place: string };
export type Bids = { won: Bid[]; history: Bid[]; todo: BidTodo[] };
export type BidIn = {
  item_id: string;
  sale_date: string;
  outcome: string;
  my_bid_krw?: number | null;
  winning_bid_krw?: number | null;
  second_bid_krw?: number | null;
  bidder_count?: number | null;
  pay_date?: string | null;
};

// 로그인한 사람의 자료. 토큰은 Supabase 세션에서.
async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBaseUrl}/me${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const meApi = {
  watch: (t: string) => call<WatchCard[]>(t, "/watch"),
  watchIds: (t: string) => call<string[]>(t, "/watch/ids"),
  addWatch: (t: string, id: string) =>
    call(t, `/watch/${encodeURIComponent(id)}`, { method: "PUT" }),
  removeWatch: (t: string, id: string) =>
    call(t, `/watch/${encodeURIComponent(id)}`, { method: "DELETE" }),
  searches: (t: string) => call<SavedSearch[]>(t, "/searches"),
  addSearch: (t: string, name: string, filters: Record<string, unknown>) =>
    call<SavedSearch>(t, "/searches", {
      method: "POST",
      body: JSON.stringify({ name, filters, delivery: "daily" }),
    }),
  notifications: (t: string) => call<Noti[]>(t, "/notifications"),
  saveProfile: (t: string, p: { regions: string[]; cash: number | null; purpose: string | null }) =>
    call(t, "/profile", { method: "PUT", body: JSON.stringify(p) }),
  bids: (t: string) => call<Bids>(t, "/bids"),
  saveBid: (t: string, b: BidIn) => call(t, "/bids", { method: "PUT", body: JSON.stringify(b) }),
  addPush: (t: string, sub: { endpoint: string; p256dh: string; auth: string }) =>
    call(t, "/push", { method: "POST", body: JSON.stringify(sub) }),
};
