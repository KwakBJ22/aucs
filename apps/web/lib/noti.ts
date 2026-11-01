// 알림이 지났는지(11/1): 「오늘 입찰일」 알림이 12일 뒤에도 「할 일·마감」 맨 위에 있었음.
// 입찰일 아침은 그날까지만, 명세서 공개는 14일, 마감 알림은 7일 지나면 「지난 할 일」로.
const KEEP_DAYS: [(k: string) => boolean, number][] = [
  [(k) => k === "bid_morning", 0],
  [(k) => k === "spec_open", 14],
  [(k) => k.startsWith("deadline_"), 7],
];

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function isStale(
  n: { kind?: string | null; created_at: string },
  now = new Date(),
): boolean {
  const k = n.kind ?? "";
  const rule = KEEP_DAYS.find(([f]) => f(k));
  if (!rule) return false;
  const made = new Date(n.created_at);
  const until = new Date(made.getFullYear(), made.getMonth(), made.getDate() + rule[1]);
  return dayKey(now) > dayKey(until);
}
