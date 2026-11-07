import { copy } from "@/lib/copy.ko";

// 인쇄·PDF 맨 위 한 줄(11/7): 보고서·입찰표·사건 문건이 같은 모양 — 「옥스 ○○ · 사건 · 기준일」
// screen=false 면 화면에서는 숨기고 인쇄에만 나옴
export function PrintHead({
  title,
  sub,
  date,
  screen = false,
}: {
  title: string;
  sub?: string;
  date: string;
  screen?: boolean;
}) {
  return (
    <header className={`report-head${screen ? "" : " print-only"}`}>
      <div>
        <b>{title}</b>
        {sub ? ` · ${sub}` : ""}
      </div>
      <div>{copy.report.basis(date)}</div>
    </header>
  );
}
