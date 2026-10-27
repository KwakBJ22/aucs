// 최근 본 물건(WATCH-01 「최근 본」): 이 기기에만, 20개까지. 저장이 안 되는 브라우저에서도 화면은 동작.
export type Recent = { id: string; label: string; at: number };
const KEY = "aucs_recent_items";

export function loadRecent(): Recent[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as Recent[];
  } catch {
    return [];
  }
}

export function rememberItem(id: string, label: string): void {
  try {
    const list = [{ id, label, at: Date.now() }, ...loadRecent().filter((x) => x.id !== id)];
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, 20)));
  } catch {
    /* 저장 못 해도 계속 */
  }
}
