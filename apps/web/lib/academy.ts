"use client";

import { LEVELS, STAGES, type Lesson, type Level, type Stage } from "@/lib/academy.ko";
import { meApi } from "@/lib/api/me";

// 아카데미 진도: 로그인 전에도 들을 수 있어 이 기기에 적어 두고(개인정보 없음 — 들은 수업 열쇠뿐),
// 로그인하면 계정에도 적음(11/14 대표님 — 다른 기기에서도 이어지게). 둘을 합친 것이 내 진도.
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

// 기기 진도와 계정 진도를 합침: 계정에 있는 것은 기기에, 기기에만 있는 것은 계정에. 합친 목록과 받은 포인트 단계를 돌려줌.
export async function syncProgress(token: string): Promise<{ done: string[]; stages: string[] }> {
  const x = await meApi.academy(token);
  const server = x.done ?? [];
  const local = doneLessons();
  const all = [...new Set([...server, ...local])];
  if (all.length > local.length) {
    try {
      localStorage.setItem(KEY, JSON.stringify(all));
    } catch {
      // 그대로
    }
  }
  const missing = local.filter((k) => !server.includes(k));
  if (missing.length) meApi.academyMark(token, missing).catch(() => undefined);
  return { done: all, stages: x.stages };
}

// 방금 들은 수업 · 해 본 과제를 적음(기기 + 로그인했으면 계정)
export function mark(key: string, token?: string): string[] {
  const list = markLesson(key);
  if (token) meApi.academyMark(token, [key]).catch(() => undefined);
  return list;
}

// ── 차례(11/14 대표님): 아무 수업이나 열지 못하게, 처음부터 차근차근.
// 등급 안에서는 앞 수업을 들어야 다음 수업이 열림. 초급은 건너뛰고 중급부터 해도 되지만,
// 고급은 중급을 다 들어야 열림(옥스를 직접 써 보는 과제가 중급에 있어서 — 고급부터 가면 옥스를 익힐 기회가 없음).
export const levelLessons = (level: Level): Lesson[] =>
  STAGES.filter((s) => s.level === level).flatMap((s) => s.lessons);

export function isOpen(key: string, done: string[]): boolean {
  if (done.includes(key)) return true; // 들은 수업은 언제든 다시
  for (const lv of LEVELS) {
    const list = levelLessons(lv.key);
    const i = list.findIndex((l) => l.key === key);
    if (i < 0) continue;
    if (lv.key === "adv" && !levelLessons("mid").every((l) => done.includes(l.key))) return false;
    return list.slice(0, i).every((l) => done.includes(l.key));
  }
  return false;
}

// 이어서 들을 수업: 중급을 시작했으면 중급(다 들었으면 고급), 아니면 초급(다 들었으면 중급)
export function nextLesson(done: string[]): Lesson | null {
  const first = (lv: Level) => levelLessons(lv).find((l) => !done.includes(l.key)) ?? null;
  const midStarted = levelLessons("mid").some((l) => done.includes(l.key));
  return (midStarted ? null : first("basic")) ?? first("mid") ?? first("adv");
}

// 이 수업 다음에 들을 수업(단계 · 등급을 넘어 이어짐)
export function lessonAfter(key: string): Lesson | null {
  const all = LEVELS.flatMap((lv) => levelLessons(lv.key));
  const i = all.findIndex((l) => l.key === key);
  return i >= 0 ? (all[i + 1] ?? null) : null;
}

export const count = (list: Lesson[], done: string[]) => ({
  n: list.filter((l) => done.includes(l.key)).length,
  total: list.length,
});

// 옥스 활용(11/14 대표님 — 경매를 아는 것만큼 옥스를 쓸 줄 아는 것도 지표): 해 본 과제 수
export function taskCount(done: string[]) {
  const tasks = STAGES.flatMap((s) => s.lessons).filter((l) => l.task);
  return { n: tasks.filter((l) => done.includes(`task:${l.key}`)).length, total: tasks.length };
}

// 단계를 누르면 갈 수업: 안 들은 첫 수업(열려 있을 때), 다 들었으면 첫 수업(다시 보기), 잠겼으면 null
export function stageEntry(s: Stage, done: string[]): Lesson | null {
  const todo = s.lessons.find((l) => !done.includes(l.key));
  if (!todo) return s.lessons[0] ?? null;
  return isOpen(todo.key, done) ? todo : null;
}
