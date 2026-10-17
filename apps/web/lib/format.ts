// 금액은 억·만 단위로 (「7억 1,050만」), 퍼센트는 정수.
export function won(n: number | null | undefined): string {
  if (n == null) return "-";
  const man = Math.round(n / 10_000);
  const eok = Math.floor(man / 10_000);
  const rest = man % 10_000;
  if (eok && rest) return `${eok}억 ${rest.toLocaleString("ko-KR")}만`;
  if (eok) return `${eok}억`;
  return `${rest.toLocaleString("ko-KR")}만`;
}

export function dday(d: number | null): string {
  if (d == null) return "";
  return d === 0 ? "D-day" : `D-${d}`;
}
