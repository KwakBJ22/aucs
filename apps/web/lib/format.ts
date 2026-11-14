// 금액은 억·만 단위로 (「7억 1,050만」), 퍼센트는 정수.
// 「3억 2,400만」의 빈칸은 줄이 안 갈라지는 빈칸(NBSP) — 좁은 칸에서 금액이 두 줄로 쪼개지지 않게(11/11)
const NB = "\u00a0";
export function won(n: number | null | undefined): string {
  if (n == null) return "-";
  const man = Math.round(n / 10_000);
  if (man >= 100_000_000) {
    // 1조 이상: 「4조 7,624억」
    const jo = Math.floor(man / 100_000_000);
    const restEok = Math.floor((man % 100_000_000) / 10_000);
    return restEok ? `${jo}조${NB}${restEok.toLocaleString("ko-KR")}억` : `${jo}조`;
  }
  const eok = Math.floor(man / 10_000);
  const rest = man % 10_000;
  const e = eok.toLocaleString("ko-KR");
  if (eok && rest) return `${e}억${NB}${rest.toLocaleString("ko-KR")}만`;
  if (eok) return `${e}억`;
  return `${rest.toLocaleString("ko-KR")}만`;
}

// 그래프 눈금용 짧은 금액(11/7): 1억 이상은 「10.4억」, 그 아래는 「9,800만」
export function wonShort(n: number | null | undefined): string {
  if (n == null) return "-";
  const eok = n / 100_000_000;
  if (eok >= 1) return `${(Math.round(eok * 10) / 10).toLocaleString("ko-KR")}억`;
  return `${Math.round(n / 10_000).toLocaleString("ko-KR")}만`;
}

// 오늘 날짜(한국 시간) 「2026-11-07」 — 인쇄 머리 기준일
// 서버 시각 글자 → 시각(11/8). 아이폰 사파리는 「2026-11-08 12:00」(가운데 빈칸)이나
// 「+00」(분 없는 시간대)을 못 읽어 Invalid Date가 됨 — 모든 화면이 이 한 곳으로 읽음
export function parseTime(s: string): Date {
  const iso = s
    .trim()
    .replace(" ", "T")
    .replace(/(T\d\d:\d\d\S*[+-]\d\d)$/, "$1:00"); // 날짜만 있으면(2026-11-01) 그대로 — 끝의 -01 은 시간대가 아님
  return new Date(iso);
}

export function todayKst(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

// 입찰일 색(11/8 한 곳): 지남 · 7일 안(급함) · 그 뒤. 카드·상세·관심·내 경매가 모두 이 기준
export const SOON_DAYS = 7;
export function ddayTone(d: number | null | undefined): "past" | "soon" | "later" {
  if (d == null) return "later";
  if (d < 0) return "past";
  return d <= SOON_DAYS ? "soon" : "later";
}

// 지난 날은 「D--8」이 아니라 「8일 지남」
export function dday(d: number | null): string {
  if (d == null) return "";
  if (d < 0) return `${-d}일 지남`;
  return d === 0 ? "D-day" : `D-${d}`;
}
