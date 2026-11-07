// 금액은 억·만 단위로 (「7억 1,050만」), 퍼센트는 정수.
export function won(n: number | null | undefined): string {
  if (n == null) return "-";
  const man = Math.round(n / 10_000);
  if (man >= 100_000_000) {
    // 1조 이상: 「4조 7,624억」
    const jo = Math.floor(man / 100_000_000);
    const restEok = Math.floor((man % 100_000_000) / 10_000);
    return restEok ? `${jo}조 ${restEok.toLocaleString("ko-KR")}억` : `${jo}조`;
  }
  const eok = Math.floor(man / 10_000);
  const rest = man % 10_000;
  const e = eok.toLocaleString("ko-KR");
  if (eok && rest) return `${e}억 ${rest.toLocaleString("ko-KR")}만`;
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
export function todayKst(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

// 지난 날은 「D--8」이 아니라 「8일 지남」
export function dday(d: number | null): string {
  if (d == null) return "";
  if (d < 0) return `${-d}일 지남`;
  return d === 0 ? "D-day" : `D-${d}`;
}
