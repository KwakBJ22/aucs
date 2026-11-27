import { copy } from "@/lib/copy.ko";

// 복사한 줄 표시(11/27 대표님): 어느 물건을 복사했는지 이 브라우저에 7일 남김.
// 막힌 브라우저(사생활 보호 · 저장 막음)면 표시만 빠지고 나머지는 그대로 동작함.
const KEY = "aucs_admin_copied";
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

// 7일 지난 것은 읽을 때 지우고, 지운 것이 있으면 저장도 다시 함
function read(): Record<string, number> {
  try {
    const raw = window.localStorage.getItem(KEY);
    const m = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
    const now = Date.now();
    const kept: Record<string, number> = {};
    for (const [k, v] of Object.entries(m))
      if (typeof v === "number" && now - v < WEEK_MS) kept[k] = v;
    if (Object.keys(kept).length !== Object.keys(m).length)
      window.localStorage.setItem(KEY, JSON.stringify(kept));
    return kept;
  } catch {
    return {};
  }
}

export function markCopied(key: string): void {
  try {
    const m = read();
    m[key] = Date.now();
    window.localStorage.setItem(KEY, JSON.stringify(m));
  } catch {
    // 막힌 브라우저 — 표시만 안 남김
  }
}

export function copiedAt(key: string): number | null {
  return read()[key] ?? null;
}

const pad = (n: number) => String(n).padStart(2, "0");

// 칩 글자: 오늘이면 「복사함 21:58」, 그 전이면 「11/26 복사함」
export function copiedText(ms: number): string {
  const d = new Date(ms);
  if (d.toDateString() === new Date().toDateString())
    return copy.admin.copiedChip.today(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
  return copy.admin.copiedChip.before(`${d.getMonth() + 1}/${d.getDate()}`);
}
