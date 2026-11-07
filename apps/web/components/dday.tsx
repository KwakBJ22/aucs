import { dday, ddayTone } from "@/lib/format";

// 입찰일 글자 하나(11/8): 색은 ddayTone 한 곳(지남 회색 · 7일 안 빨강 · 그 뒤 주황). children 이 있으면 그 글자로.
export function DDay({
  d,
  className = "",
  children,
}: {
  d: number | null | undefined;
  className?: string;
  children?: React.ReactNode;
}) {
  return <b className={`dd-${ddayTone(d)} ${className}`.trim()}>{children ?? dday(d ?? null)}</b>;
}
