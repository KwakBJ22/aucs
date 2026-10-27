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
  if (eok && rest) return `${eok}억 ${rest.toLocaleString("ko-KR")}만`;
  if (eok) return `${eok}억`;
  return `${rest.toLocaleString("ko-KR")}만`;
}

// 지난 날은 「D--8」이 아니라 「8일 지남」
export function dday(d: number | null): string {
  if (d == null) return "";
  if (d < 0) return `${-d}일 지남`;
  return d === 0 ? "D-day" : `D-${d}`;
}
