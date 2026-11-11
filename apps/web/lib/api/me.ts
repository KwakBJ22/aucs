import { ApiError, apiBaseUrl, clearMeCache, getMine } from "./client";
import type { ServerProfile } from "@/lib/profile";
import type { Calc, ItemCard, ItemDetail, OnbidDetail, Schedule } from "./items";

export type WatchStep = "found" | "review" | "field" | "money" | "bid" | "result" | "after";
export const WATCH_STEPS: WatchStep[] = [
  "found",
  "review",
  "field",
  "money",
  "bid",
  "result",
  "after",
];
export type WatchCard = ItemCard & {
  step: WatchStep;
  in_compare: boolean;
  changed?: boolean;
  last_result?: {
    result: string;
    winning_bid_krw: number | null;
    sale_rate: number | null;
    date: string;
  } | null;
};
export type Compare = {
  items: string[];
  excluded: {
    item_id: string;
    reason: string;
    at: string;
    case_no: string | null;
    place: string | null;
  }[];
  max: number;
};
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
  kind?: string | null;
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

export type LadderRow = {
  section: string;
  rank_no: string;
  name: string;
  date: string | null;
  amount_krw: number | null;
  holder: string;
  judgment: string;
  is_base: boolean;
  mark: "추정" | "내가 고침" | null;
};
export type Ladder = {
  base: { name: string; date: string | null } | null;
  rows: LadderRow[];
  tenants: {
    name: string | null;
    move_in: string | null;
    deposit_krw: number | null;
    verdict: string;
    power: boolean | null;
  }[];
  hold_krw: number;
  line: string;
  state: string;
  spec_check?: { same: boolean; spec: string; spec_date: string; registry_date: string } | null;
  payout: {
    price_krw: number;
    rows: { name: string; claim_krw: number | null; paid_krw: number }[];
    surplus_krw: number;
    unknown: string[];
  } | null;
};
export type RegistryUpload = {
  upload_id: number;
  file_name: string | null;
  status: "processing" | "parsed" | "failed";
  method: string | null;
  error: string | null;
  delete_after: string;
  ladder: Ladder | null;
  created_at?: string;
  mine?: boolean; // false 면 다른 회원이 올려 공개된 등기부(11/12)
  points?: { points: number; why: string } | null;
  choices?: Record<string, string[]>;
  address?: {
    result: "same" | "unit_differs" | "different" | "unknown";
    registry?: string;
    item?: string;
    registry_unit?: string | null;
    item_unit?: string | null;
    ok: boolean;
  };
};

// 등기부 PDF 올리기. 먼저 파일 보관함(registry-uploads/<회원>/…)에 바로 올리고 API 는 그걸 가져감(11/3 —
// 서버(Vercel)가 한 번에 4.5MB 까지만 받아서). 보관함이 안 되면 예전처럼 API 로 직접(multipart).
export async function uploadRegistry(token: string, itemId: string, file: File): Promise<void> {
  const { supabase } = await import("@/lib/auth");
  const uid = supabase ? (await supabase.auth.getSession()).data.session?.user.id : undefined;
  if (supabase && uid) {
    const path = `${uid}/${crypto.randomUUID()}.pdf`;
    const up = await supabase.storage
      .from("registry-uploads")
      .upload(path, file, { contentType: "application/pdf" });
    if (!up.error) {
      const res = await fetch(
        `${apiBaseUrl}/me/registries/${encodeURIComponent(itemId)}/from-storage`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ path, file_name: file.name.slice(0, 120) }),
        },
      );
      clearMeCache();
      if (!res.ok) {
        const j = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(j?.detail ?? `HTTP ${res.status}`);
      }
      return;
    }
  }
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${apiBaseUrl}/me/registries/${encodeURIComponent(itemId)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!res.ok) {
    const j = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(j?.detail ?? `HTTP ${res.status}`);
  }
}

// 포인트 벌기(11/12, docs/design/11-points.md)
export type DocKind = "registry" | "appraisal";
export type PointSummary = {
  balance: number;
  today: Record<DocKind, number>;
  max: Partial<Record<DocKind, number>>;
  points: Partial<Record<DocKind, number>>;
  hold_minutes: number | null;
};
export type PointHold = { until: string | null; extended: boolean };
export type PointRow = {
  item_id: string;
  court: string;
  case_no: string;
  sale_date: string | null;
  place: string;
  building: string | null;
  need: Partial<Record<DocKind, PointHold>>;
};
export type PointResult = { ok?: boolean; points: number; why: string };

// 감정평가서 PDF 올리기: 등기부와 같이 보관함(appraisal-uploads/<회원>/…)에 바로 → API 가 받아 사건번호를 맞춰 봄
export async function uploadAppraisal(
  token: string,
  itemId: string,
  file: File,
): Promise<PointResult> {
  const { supabase } = await import("@/lib/auth");
  const uid = supabase ? (await supabase.auth.getSession()).data.session?.user.id : undefined;
  if (!supabase || !uid) throw new Error("로그인이 필요해요");
  const path = `${uid}/${crypto.randomUUID()}.pdf`;
  const up = await supabase.storage
    .from("appraisal-uploads")
    .upload(path, file, { contentType: "application/pdf" });
  if (up.error) throw new Error(up.error.message);
  return call<PointResult>(token, `/appraisals/${encodeURIComponent(itemId)}/from-storage`, {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

// 로그인한 사람의 자료. 토큰은 Supabase 세션에서.
// 읽기(GET)는 잠깐 기억하고 같은 요청은 한 번만 보냄(client.ts). 바꾸는 요청은 끝나면 기억을 비움.
// 등기부처럼 읽는 중 상태를 3초마다 확인하는 것은 fresh 로 기억을 건너뜀.
async function call<T>(
  token: string,
  path: string,
  init?: RequestInit & { fresh?: boolean },
): Promise<T> {
  const method = init?.method ?? "GET";
  if (method === "GET" && !init?.fresh) return getMine<T>(token, `/me${path}`);
  try {
    const res = await fetch(`${apiBaseUrl}/me${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
      },
      cache: "no-store",
    });
    if (!res.ok) throw new ApiError(res.status);
    return (await res.json()) as T;
  } finally {
    if (method !== "GET") clearMeCache();
  }
}

export type Workspace = {
  step: WatchStep;
  memo: string;
  checks: Record<string, string>;
  calcs: { bid_krw: number; cash_krw: number | null; saved_at: string }[];
  history: { at: string; what: string; change: string }[];
};

export type CompareFull = Compare & {
  cols: {
    id: string;
    d: ItemDetail | OnbidDetail | null;
    calc: Calc | null;
    w: Workspace | null;
  }[];
};

export type MockIn = {
  item_id: string;
  decision: "bid" | "skip";
  bid_krw: number | null;
  max_krw: number | null;
  reason: string | null;
};
export type Mock = MockIn & {
  mock_id: number;
  sale_date: string;
  place: string | null;
  review: string[];
  // 떨어졌을 때: 같은 구·같은 종류, 내 금액(상한) 안에서 시작하는 진행 물건
  similar?: { item_id: string; place: string; sale_date: string; min_price_krw: number }[];
};

export type MyInquiry = {
  inquiry_id: number;
  body: string;
  answer: string | null;
  created_at: string;
};
export type Payment = {
  payment_id: number;
  plan: string;
  period: "month" | "year" | "one";
  amount_krw: number;
  item_id: string | null;
  status: "paid" | "cancelled" | "refunded" | "part_refunded";
  refunded_krw: number;
  auto_renew: boolean;
  method_note: string | null;
  order_id: string | null;
  receipt_url: string | null;
  paid_at: string;
  valid_from: string;
  valid_to: string;
  refund_status: "waiting" | "done" | "rejected" | null;
  refund: { amount_krw: number; rule: string } | null;
};
export type Billing = {
  current: {
    plan: string;
    until: string;
    auto_renew: boolean;
    period: string;
    amount_krw: number;
    item_id: string | null;
  }[];
  payments: Payment[];
  grants: { plan: string; until_date: string; reason: string; created_at: string }[];
};
export const meApi = {
  // 화면 한 번에(11/3): 내 경매 = 관심·입찰 기록·모의입찰, 내 정보 = 알림 조건·문의
  auction: (t: string) => call<{ watch: WatchCard[]; bids: Bids; mocks: Mock[] }>(t, "/auction"),
  // 관심 물건 한 칸 = 물건 상세 + 내 작업 공간(PC 관심 오른쪽·현장 확인)
  panel: (t: string, id: string) =>
    call<{ d: import("./items").ItemDetail | null; w: Workspace }>(
      t,
      `/watch/${encodeURIComponent(id)}/panel`,
    ),
  more: (t: string) => call<{ searches: SavedSearch[]; inquiries: MyInquiry[] }>(t, "/more"),
  billing: (t: string) => call<Billing>(t, "/billing", { fresh: true }),
  refund: (t: string, id: number, reason?: string) =>
    call<{ estimate_krw: number; rule: string; stopped?: boolean }>(t, `/billing/${id}/refund`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  stopRenew: (t: string, id: number) => call(t, `/billing/${id}/stop-renew`, { method: "POST" }),
  inquiries: (t: string) => call<MyInquiry[]>(t, "/inquiries", { fresh: true }),
  ask: (t: string, body: string) =>
    call(t, "/inquiries", { method: "POST", body: JSON.stringify({ body }) }),
  mocks: (t: string) => call<Mock[]>(t, "/mocks"),
  saveMock: (t: string, m: MockIn) =>
    call(t, "/mocks", { method: "POST", body: JSON.stringify(m) }),
  removeMock: (t: string, id: number) => call(t, `/mocks/${id}`, { method: "DELETE" }),
  deleteAccount: (t: string) => call(t, "/account", { method: "DELETE" }),
  compare: (t: string) => call<Compare>(t, "/compare"),
  /** 비교함 화면 전부(담은 물건마다 상세·계산·작업 공간) 한 번에. */
  compareFull: (t: string, homes: number, first: boolean) =>
    call<CompareFull>(t, `/compare/full?homes=${homes}${first ? "&first=true" : ""}`),
  addCompare: (t: string, id: string) =>
    call(t, `/compare/${encodeURIComponent(id)}`, { method: "PUT" }),
  removeCompare: (t: string, id: string) =>
    call(t, `/compare/${encodeURIComponent(id)}`, { method: "DELETE" }),
  exclude: (t: string, id: string, reason: string) =>
    call(t, `/compare/${encodeURIComponent(id)}/exclude`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  unexclude: (t: string, id: string) =>
    call(t, `/compare/excluded/${encodeURIComponent(id)}`, { method: "DELETE" }),
  workspace: (t: string, id: string) =>
    call<Workspace>(t, `/watch/${encodeURIComponent(id)}/workspace`),
  saveMemo: (t: string, id: string, memo: string) =>
    call(t, `/watch/${encodeURIComponent(id)}/memo`, {
      method: "PUT",
      body: JSON.stringify({ memo }),
    }),
  check: (t: string, id: string, key: string, done: boolean) =>
    call(t, `/watch/${encodeURIComponent(id)}/check`, {
      method: "PUT",
      body: JSON.stringify({ key, done }),
    }),
  addCalc: (t: string, id: string, bid_krw: number, cash_krw: number | null) =>
    call(t, `/watch/${encodeURIComponent(id)}/calcs`, {
      method: "POST",
      body: JSON.stringify({ bid_krw, cash_krw }),
    }),
  removeCalc: (t: string, id: string, bid: number) =>
    call(t, `/watch/${encodeURIComponent(id)}/calcs/${bid}`, { method: "DELETE" }),
  watch: (t: string) => call<WatchCard[]>(t, "/watch"),
  /** 홈 화면 내 자료 한 번에(관심·알림·비교함에서 뺀 물건). */
  home: (t: string) =>
    call<{ watch: WatchCard[]; notifications: Noti[]; excluded: string[] }>(t, "/home"),
  watchIds: (t: string) => call<string[]>(t, "/watch/ids"),
  addWatch: (t: string, id: string) =>
    call(t, `/watch/${encodeURIComponent(id)}`, { method: "PUT" }),
  setStep: (t: string, id: string, step: WatchStep) =>
    call(t, `/watch/${encodeURIComponent(id)}/step`, {
      method: "PUT",
      body: JSON.stringify({ step }),
    }),
  removeWatch: (t: string, id: string) =>
    call(t, `/watch/${encodeURIComponent(id)}`, { method: "DELETE" }),
  searches: (t: string) => call<SavedSearch[]>(t, "/searches"),
  addSearch: (t: string, name: string, filters: Record<string, unknown>) =>
    call<SavedSearch>(t, "/searches", {
      method: "POST",
      body: JSON.stringify({ name, filters, delivery: "daily" }),
    }),
  removeSearch: (t: string, id: number) => call(t, `/searches/${id}`, { method: "DELETE" }),
  notifications: (t: string) => call<Noti[]>(t, "/notifications"),
  profile: (t: string) => call<ServerProfile | null>(t, "/profile", { fresh: true }),
  saveProfile: (t: string, p: Record<string, unknown>) =>
    call(t, "/profile", { method: "PUT", body: JSON.stringify(p) }),
  bids: (t: string) => call<Bids>(t, "/bids"),
  points: (t: string) => call<PointSummary>(t, "/points", { fresh: true }),
  pointsBoard: (t: string) => call<PointRow[]>(t, "/points/board", { fresh: true }),
  hold: (t: string, id: string, kind: DocKind, extend = false) =>
    call<PointHold>(t, `/points/hold/${encodeURIComponent(id)}/${kind}?extend=${extend}`, {
      method: "POST",
    }),
  registry: (t: string, id: string) =>
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}`, { fresh: true }),
  acceptAddress: (t: string, id: string) =>
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}/address-ok`, {
      method: "POST",
    }),
  fixRight: (t: string, id: string, b: { section: string; rank_no: string; purpose: string }) =>
    call<RegistryUpload | null>(t, `/registries/${encodeURIComponent(id)}/rights`, {
      method: "PATCH",
      body: JSON.stringify(b),
    }),
  saveBid: (t: string, b: BidIn) => call(t, "/bids", { method: "PUT", body: JSON.stringify(b) }),
  report: (t: string, b: { item_id: string; section: string; note: string }) =>
    call<{ report_id: number }>(t, "/reports", { method: "POST", body: JSON.stringify(b) }),
  addPush: (t: string, sub: { endpoint: string; p256dh: string; auth: string }) =>
    call(t, "/push", { method: "POST", body: JSON.stringify(sub) }),
};
