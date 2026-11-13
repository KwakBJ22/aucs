"use client";

// 아카데미 진도: 로그인 전에도 들을 수 있어 이 기기에 적어 둠(개인정보 없음 — 들은 수업 열쇠뿐).
// 포인트는 로그인한 뒤 서버가 단계마다 한 번 줌.
const KEY = "aucs_academy";

export function doneLessons(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]") as unknown;
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function markLesson(key: string): string[] {
  const list = [...new Set([...doneLessons(), key])];
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // 저장이 막힌 브라우저 — 이번 화면에서만 기억
  }
  return list;
}
