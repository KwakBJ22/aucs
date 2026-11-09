import { getJson, postQuiet } from "./client";

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
export type Source = "all" | "court" | "onbid";
export type ItemCard = {
  item_id: string;
  photo?: string | null; // 첫 사진(없으면 카드에 종류 아이콘, 11/9)
  source?: "court" | "onbid"; // 공매(온비드)는 경매와 같은 카드 + 아래 칸(10/28)
  kind?: string;
  kind_name?: string;
  bid_end?: string | null;
  next_round?: { min_price_krw: number; bid_end: string | null } | null;
  court: string;
  case_no: string;
  sale_date: string | null;
  d_day: number | null;
  usage: string | null;
  usage_kind?: string; // 종류(apt·officetel·villa·house·shop·land·etc) — 판정은 API 규칙 한 곳(11/8)
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
export type ResultCard = {
  result_id: number;
  item_id: string | null;
  court: string;
  case_no: string;
  sale_date: string;
  result: string;
  usage: string | null;
  place: string;
  building: string | null;
  appraisal_krw: number | null;
  winning_bid_krw: number | null;
  sale_rate: number | null;
};
export type FindStatus = "active" | "sold" | "withdrawn" | "all";
export type ItemList = {
  total: number;
  items: ItemCard[];
  results?: ResultCard[];
  exact_item_id?: string | null;
};
export type RegionRow = { sido: string; sigungu: string; items: number };

// 찾기 조건(FIND-03). 금액은 원, 면적은 ㎡.
export type FindFilter = {
  usage?: string[];
  exclude?: string[];
  failed_min?: number;
  rate_max?: number;
  days_max?: number;
  area_min?: number;
  area_max?: number;
  price_max?: number;
};
export const SAFE_MODE = ["share", "lien", "senior", "superficies", "villa", "special", "stop"];

export function fetchItems(opts: {
  sigungu?: string[];
  maxCash?: number | null;
  sort?: "deadline" | "rate";
  limit?: number;
  q?: string;
  status?: FindStatus;
  filter?: FindFilter;
  source?: Source;
  homes?: number | null; // 가진 집 수 — 「가진 현금」을 실제 필요한 현금(대출 감안)으로 견줌(11/9)
}): Promise<ItemList> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.filter ?? {})) {
    if (v == null) continue;
    if (Array.isArray(v)) v.forEach((x) => q.append(k, String(x)));
    else q.set(k, String(v));
  }
  if (opts.q) q.set("q", opts.q);
  if (opts.status) q.set("status", opts.status);
  if (opts.source && opts.source !== "all") q.set("source", opts.source);
  (opts.sigungu ?? []).forEach((s) => q.append("sigungu", s));
  if (opts.maxCash) q.set("max_cash", String(opts.maxCash));
  if (opts.maxCash && opts.homes) q.set("homes", String(opts.homes));
  if (opts.sort) q.set("sort", opts.sort);
  if (opts.limit) q.set("limit", String(opts.limit));
  return getJson<ItemList>(`/items?${q.toString()}`);
}

// 지역별 물건 수는 하루 한 번 바뀜 → 30분 기억(찾기·시작·전문가 화면을 오가도 다시 부르지 않음, 11/3)
export const fetchRegions = () => getJson<RegionRow[]>("/regions", 30 * 60_000);

// 홈 공개 자료 한 번에(11/3): 내 조건 물건 20 · 이번 주 마감 공매 5 · (PC) 석 달 낙찰가율 · 게시 중 공지
// 홈 추천 카드(11/4): 카드 + 추천 점수·이유·사진·공고 전 여부·유찰 예상
export type FailOdds = { fail: number; n: number; pct: number; of10: number; likely: boolean };
export type PickCard = ItemCard & {
  fail_odds?: FailOdds | null;
  score: number;
  reasons: string[];
  preview: boolean; // 유찰 뒤 다음 기일이 잡힌 물건(법원 공고 전)
  likely_fail: boolean; // 이번엔 유찰될 것 같은 물건
  next_min_krw?: number | null; // 유찰되면 다음 최저가
};
export type HomeFeed = {
  mine: ItemList;
  picks?: PickCard[];
  soon?: PickCard[];
  next?: PickCard[];
  onbid_soon: ItemList | null;
  market: import("./pro").Market | null;
  notices: { notice_id: number; title: string; body: string }[];
};
// 모아 보기(11/7): 모음마다 건수와 물건(why = 이 모음에 든 이유 한 줄)
export type CollectionCard = PickCard & { why: string };
export type Collections = Record<string, { total: number; items: CollectionCard[] }>;
export function fetchCollections(opts: {
  sigungu?: string[];
  maxCash?: number | null;
  key?: string;
  limit?: number;
  homes?: number | null;
}) {
  const q = new URLSearchParams();
  (opts.sigungu ?? []).forEach((s) => q.append("sigungu", s));
  if (opts.maxCash) q.set("max_cash", String(opts.maxCash));
  if (opts.maxCash && opts.homes) q.set("homes", String(opts.homes));
  if (opts.key) q.set("key", opts.key);
  if (opts.limit) q.set("limit", String(opts.limit));
  return getJson<Collections>(`/collections?${q.toString()}`);
}

// 게시 중인 공지(공개) — 고객센터(11/7)
export type PublicNotice = { notice_id: number; title: string; body: string; start_at: string };
export const fetchNotices = () => getJson<PublicNotice[]>("/notices");

export function fetchHomeFeed(opts: {
  sigungu?: string[];
  maxCash?: number | null;
  market?: boolean;
  purpose?: string | null;
  homes?: number | null;
}) {
  const q = new URLSearchParams();
  if (opts.purpose) q.set("purpose", opts.purpose);
  (opts.sigungu ?? []).forEach((s) => q.append("sigungu", s));
  if (opts.maxCash) q.set("max_cash", String(opts.maxCash));
  if (opts.market) q.set("market", "true");
  if (opts.maxCash && opts.homes) q.set("homes", String(opts.homes));
  return getJson<HomeFeed>(`/home-feed?${q.toString()}`);
}

export type Question = {
  key: "buy" | "hold" | "worth" | "cost" | "check";
  title: string;
  answer: string;
  tone: "green" | "gray" | "orange" | "red" | "blue";
  body: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
};
// 관할 법원 평균 응찰자 수(회원 기록, 5건부터 avg)
export type CourtBidders = { n: number; avg: number | null; median: number | null; min_n: number };
export const fetchCourtBidders = (id: string) =>
  getJson<CourtBidders>(`/items/${encodeURIComponent(id)}/court-bidders`);
// 관심도(경쟁 신호) — 적으면 서버가 비워 보냄
export type Interest = { viewers_7d: number; watchers: number };
export type SameHouse = {
  source: Source;
  item_id: string;
  no: string;
  date: string | null;
  min_price_krw: number | null;
};

export type ItemDetail = ItemCard & {
  verdict: string;
  fatal: string | null;
  address: string | null;
  sale_place: string | null;
  dept_name: string | null;
  next_round: {
    min_price_krw: number | null;
    reduction_pct: number | null;
    verified: boolean;
    fail_odds?: FailOdds | null; // 같은 법원·종류·회차 실제 유찰 비율(WAIT-01, 11/7)
  };
  rounds: { sale_date: string; min_price_krw: number | null; result: string }[];
  tags: { label: string; ok: boolean }[];
  questions: Question[];
  failure_types: { code: string; title: string }[];
  failure_table?: {
    code: string;
    title: string;
    state: "걸림" | "확인 필요" | "확인함" | "대비됨" | "해당 없음" | "자료 기다림"; // 11/4 신호 없음을 나눔
    why: string;
  }[];
  schedule: Schedule;
  same_house?: SameHouse[];
  interest?: Interest | null;
  court_bidders?: CourtBidders | null;
  photos?: string[];
  appraisal?: {
    points: { label: string; text: string }[];
    firm: string | null;
    price_date?: string | null; // 가격시점 2022.03.22
    parts?: AppraisalParts | null; // 감정가 나눔(11/7)
  } | null; // 감정평가 요점(11/4)
  outcome?: Outcome | null; // 지난 기일 결과(앞으로 잡힌 기일이 없을 때, 11/1) // 법원 현장 사진(휴대폰 크기, 매각 뒤 30일 지나면 없음)
  computed_at: string | null;
};

// 감정가 나눔(11/7, 물건상세): 토지·건물 금액 · 제시외 건물 · 대지권
export type AppraisalParts = {
  kind: "land_only" | "building_only" | "land_and_building" | "unit" | null;
  land_krw: number | null;
  building_krw: number | null;
  unit_krw: number | null;
  building_pct: number | null;
  extras: {
    use: string | null;
    area_m2: number | null;
    structure: string | null;
    krw: number | null;
  }[];
  extras_krw: number | null;
  land_right_m2: number | null;
  land_total_m2: number | null;
};

export const fetchItem = (id: string) => getJson<ItemDetail>(`/items/${encodeURIComponent(id)}`);

// 공매 상세(10/28, 설계서 4절) — /items/OB-… 이 돌려줌
export type OnbidRound = {
  label: "지난" | "이번" | "다음";
  bid_start?: string | null;
  bid_end: string | null;
  open_at: string | null;
  min_price_krw: number | null;
  rate: number | null;
  result: string | null;
};
export type OnbidExpected = {
  bucket: string;
  n: number;
  share: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  price_krw: number | null;
};
export type OnbidDetail = ItemCard & {
  source: "onbid";
  title: string | null;
  address: string | null;
  bid_start: string | null;
  open_at: string | null;
  status_name: string | null;
  gone: boolean;
  notice: { no: string | null; date: string | null; name: string | null; org: string | null };
  verdict: string;
  fatal: string | null;
  warnings: string[];
  missing_docs: string[];
  rounds: OnbidRound[];
  wait_line: string | null;
  market: {
    price_krw: number;
    lo_krw: number;
    hi_krw: number;
    n: number;
    recent: { date: string; floor: number | null; price_krw: number }[];
  } | null;
  market_rate: number | null;
  appraisal_vs_market: number | null;
  expected: OnbidExpected[];
  expected_basis: string;
  checklist: { key: string; label: string; state: string; what: string }[];
  check_left: number;
  same_house?: SameHouse[];
  interest?: Interest | null;
  building?: import("@/components/item/building").Bldg | null;
  computed_at: string;
};
export type OnbidNotice = {
  item_id: string;
  mng_no: string;
  title: string | null;
  kind_name: string | null;
  rows: { label: string; value: string }[];
};
export const fetchNotice = (id: string) =>
  getJson<OnbidNotice>(`/items/${encodeURIComponent(id)}/notice`);
export const isOnbid = (d: { source?: string }): d is OnbidDetail => d.source === "onbid";

// DOC-01 원문 보기
export type DocKind = "status_report" | "deliveries" | "spec_sheet";
export type Outcome = {
  date: string;
  code: "sold" | "failed" | "withdrawn" | "changed" | "unknown" | string;
  text: string;
  closed: boolean; // 매각·취하 — 입찰 준비는 감춤
  winning_bid_krw: number | null;
  rate: number | null;
  expected: [number, number] | null;
  within: boolean;
};

export type ItemDocs = {
  closed?: boolean; // 매각 뒤 30일 지난 사건 — 원문은 보여 주지 않음(11/1)
  spec_sheet: {
    fetched_at: string | null;
    written: string | null;
    base: string | null;
    keep: string | null;
    superficies: string | null;
    remark: string | null;
    item_remark: string | null;
  } | null;
  status_report: {
    fetched_at: string | null;
    exam_at: string | null;
    summary: string | null;
    lease_note: string | null;
    possession: string[];
    tenants: {
      name: string | null;
      part: string | null;
      use: string | null;
      move_in: string | null;
      fixed: string | null;
      deposit: string | null;
      rent: string | null;
      note: string | null;
    }[];
  } | null;
  deliveries: {
    fetched_at: string | null;
    filings: { date: string | null; text: string | null; result: string | null; key: boolean }[];
    sends: { date: string | null; text: string | null; result: string | null }[];
  } | null;
};
export const fetchDocs = (id: string) => getJson<ItemDocs>(`/items/${encodeURIComponent(id)}/docs`);

export const fetchBidCheck = (id: string, bid: number) =>
  getJson<BidCheck>(`/items/${encodeURIComponent(id)}/bid-check?bid=${bid}`);

export type CashBreakdown = {
  bid_krw: number;
  assume_krw?: number; // 떠안는 돈(넣었을 때)
  deposit_krw: number;
  loan_krw: number;
  loan: {
    pct: number;
    cap_krw: number | null;
    who: string;
    note: string | null;
    by_dsr?: boolean;
  };
  dsr: { loan_krw: number; rate_pct: number } | null;
  tax: {
    tax_krw: number;
    relief_krw: number;
    rate: number;
    total_pct: number;
    heavy: boolean;
    temporary_two: boolean;
  };
  registration_krw: number;
  move_out_krw: number;
  repair_krw: number;
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
  assume?: { risk: boolean; krw: number | null }; // 떠안는 돈(선순위 전세권·대항력 임차인 등, 11/1)
  check?: BidCheck | null; // 입찰표 실수 막기 검사(고른 입찰가 기준)
  rent?: {
    loan_krw: number;
    no_loan_reason: string | null;
    rate_pct: number;
    jeonse_n: number;
    wolse_n: number;
    jeonse?: { deposit_krw: number; cash_krw: number };
    wolse?: {
      deposit_krw: number;
      rent_krw: number;
      cash_krw: number;
      net_year_krw: number;
      yield_pct: number | null;
    };
  } | null;
  move_out?: { low_krw: number; high_krw: number; mid_krw: number; stairs: boolean } | null;
  repair?: {
    low_krw: number | null;
    high_krw: number | null;
    mid_krw: number;
    basis: string;
  } | null;
};
export function fetchCalc(
  id: string,
  o: {
    bid?: number | null;
    homes: number;
    first: boolean;
    loan?: number | null;
    selling?: boolean;
    income?: number | null;
    otherMonthly?: number | null;
    assume?: number | null;
  },
): Promise<Calc> {
  const q = new URLSearchParams({
    homes: String(o.homes),
    first: String(o.first),
    selling: String(Boolean(o.selling)),
  });
  if (o.income) q.set("income", String(o.income));
  if (o.otherMonthly) q.set("other_monthly", String(o.otherMonthly));
  if (o.bid) q.set("bid", String(o.bid));
  if (o.loan != null) q.set("loan", String(o.loan));
  if (o.assume != null) q.set("assume", String(o.assume));
  return getJson<Calc>(`/items/${encodeURIComponent(id)}/calc?${q.toString()}`);
}

// 입찰일 아침(BID-02)
export type BidDay = {
  item_id: string;
  court: string;
  court_full: string;
  dept: string | null;
  tel: string | null;
  case_no: string;
  item_no: number;
  sale_date: string | null;
  time: string | null;
  place: string | null;
  min_price_krw: number;
  deposit_krw: number;
  deposit_rate_pct: number;
  resale: boolean;
  state: "ok" | "soon" | "moved" | "gone";
  state_line: string;
  checked_at: string | null;
};
export const fetchBidDay = (id: string) =>
  getJson<BidDay>(`/items/${encodeURIComponent(id)}/bid-day`);

/** 물건 상세를 열었는데 현황조사가 없으면 서류 받기를 줄 세움(11/4 — 「자료 기다림」을 손님이 본 물건부터 채움). */
export const requestDocs = (id: string) =>
  postQuiet(`/items/${encodeURIComponent(id)}/docs-request`);
