"use client";

// 아카데미 게임 요소(11/18 대표님): 레벨은 「레벨 시험 통과」로만 오름 · 오를 때마다 축하 화면 · 칭호 · 경험치 · 연속 학습.
// 모두 진도 목록(들은 수업 · 과제 · 시험 열쇠)에서 셈 — 따로 서버에 적는 것은 없음(연속 학습 날짜만 이 기기에).
import { LEVELS, STAGES, type Level } from "@/lib/academy.ko";

// 칭호(담백하게 — 6절 「칭호 말투」 추천안)와 배지 그림
export const TITLES: Record<Level, { title: string; badge: string }> = {
  l1: { title: "경매 구경꾼", badge: "🔰" },
  l2: { title: "물건 탐색가", badge: "🧭" },
  l3: { title: "서류 읽는 사람", badge: "📄" },
  l4: { title: "권리 분석가", badge: "⚖️" },
  l5: { title: "돈 계산하는 사람", badge: "🧮" },
  l6: { title: "입찰 준비 끝", badge: "🎯" },
  l7: { title: "경매 고수", badge: "🏆" },
};

// 경험치: 수업 10 · 과제 15 · 레벨 시험 50
export const XP = { lesson: 10, task: 15, test: 50 } as const;

const lessonKeys = new Set(STAGES.flatMap((s) => s.lessons.map((l) => l.key)));

export function xpOf(done: string[]): number {
  let x = 0;
  for (const k of done) {
    if (k.startsWith("test:")) x += XP.test;
    else if (k.startsWith("task:")) x += XP.task;
    else if (lessonKeys.has(k)) x += XP.lesson;
  }
  return x;
}

/** 통과한 가장 높은 레벨(0 = 아직 없음). 레벨은 시험을 통과해야 오름. */
export function reached(done: string[]): number {
  let n = 0;
  LEVELS.forEach((lv, i) => {
    if (done.includes(`test:${lv.key}`)) n = Math.max(n, i + 1);
  });
  return n;
}

/** 지금 도전 중인 레벨(통과한 다음 레벨)과 그 레벨까지 남은 것 — 수업 + 시험 1. */
export function nextGoal(done: string[], lessonsOf: (lv: Level) => { key: string }[]) {
  const i = reached(done);
  const lv = LEVELS[i];
  if (!lv) return null;
  const ls = lessonsOf(lv.key);
  const left = ls.filter((l) => !done.includes(l.key)).length;
  return { level: lv, left, total: ls.length + 1, have: ls.length - left };
}

// 연속 학습: 수업을 끝내거나 시험을 통과한 날(이 기기)
const DAYS = "aucs_ac_days";
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function studied(): void {
  try {
    const v = JSON.parse(localStorage.getItem(DAYS) ?? "[]") as string[];
    const t = today();
    if (!v.includes(t)) localStorage.setItem(DAYS, JSON.stringify([...v.slice(-60), t]));
  } catch {
    /* 못 적어도 그대로 */
  }
}

/** 오늘(또는 어제)까지 이어진 날 수 */
export function streak(): number {
  try {
    const days = new Set(JSON.parse(localStorage.getItem(DAYS) ?? "[]") as string[]);
    const d = new Date();
    const key = (x: Date) =>
      `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
    if (!days.has(key(d))) d.setDate(d.getDate() - 1); // 오늘 아직 안 했으면 어제부터 셈
    let n = 0;
    while (days.has(key(d))) {
      n += 1;
      d.setDate(d.getDate() - 1);
    }
    return n;
  } catch {
    return 0;
  }
}
