"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LEVELS, findLesson, quizzesOf } from "@/lib/academy.ko";
import {
  count,
  doneLessons,
  isOpen,
  lessonAfter,
  levelLessons,
  mark,
  nextLesson,
  syncProgress,
} from "@/lib/academy";
import { studied } from "@/lib/academy-game";
import { taskDone, waitTask } from "@/lib/academy-hit";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.academy;

// 수업 한 편: 카드를 옆으로 넘김(손가락 · 버튼) → 마지막 장에 문제 하나 → 다 들으면 진도 저장 · 단계가 끝나면 포인트
// 11/14 대표님: 차례대로만 열림(잠긴 수업은 들을 차례인 수업으로 보냄) · 위에 어디쯤인지 · 끝 화면에 등급 진도(조금씩 채워 가는 느낌)
export default function LessonPage() {
  const { lesson: key } = useParams<{ lesson: string }>();
  const found = findLesson(decodeURIComponent(key ?? ""));
  const { session } = useSession();
  const token = session?.access_token;
  const router = useRouter();
  const rail = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState(0);
  const [picks, setPicks] = useState<Record<number, number>>({}); // 문제 번호 → 고른 답
  const [end, setEnd] = useState<{ stageDone: boolean; points: number | null } | null>(null);
  const [done, setDone] = useState<string[] | null>(null); // 기기에 적어 둔 진도(읽기 전엔 null)
  useEffect(() => {
    setDone(doneLessons());
    if (!token) return;
    let stop = false;
    syncProgress(token) // 다른 기기에서 들은 것까지 합쳐서 열렸는지 봄
      .then((x) => !stop && setDone(x.done))
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, [token]);

  if (!found)
    return (
      <main className="page">
        <PageHeader title={t.title} back="/academy" />
        <p className="sub">{t.noLesson}</p>
      </main>
    );
  const { stage, lesson } = found;
  const next = lessonAfter(lesson.key);
  const level = LEVELS.find((x) => x.key === stage.level);
  const quizzes = quizzesOf(lesson);
  const total = lesson.cards.length + quizzes.length; // 카드 + 문제(11/17 수업마다 3개)
  const answered = quizzes.every((_, i) => picks[i] !== undefined);
  const no = stage.lessons.findIndex((l) => l.key === lesson.key) + 1;

  if (done && !isOpen(lesson.key, done)) {
    const turn = nextLesson(done);
    return (
      <main className="page">
        <PageHeader title={t.title} back="/academy" />
        <section className="section ta-center">
          <h2>{t.lockedTitle}</h2>
          <p className="sub">{t.lockedSub}</p>
          {turn && (
            <Link href={`/academy/${turn.key}`} className="btn primary mt-10">
              {t.resume(turn.title)}
            </Link>
          )}
        </section>
      </main>
    );
  }

  const go = (i: number) => {
    const el = rail.current;
    if (el) el.scrollTo({ left: el.clientWidth * i, behavior: "smooth" });
  };
  const finish = () => {
    const list = mark(lesson.key, token);
    studied();
    setDone(list);
    const stageDone = stage.lessons.every((l) => list.includes(l.key));
    setEnd({ stageDone, points: null });
    if (stageDone && token && !stage.review)
      meApi
        .academyDone(token, stage.key)
        .then((x) => setEnd({ stageDone, points: x.points }))
        .catch(() => undefined);
    // 11/18 대표님: 레벨의 마지막 수업을 끝내면 레벨 시험이 바로 나옴 — 통과해야 레벨업
    const lv = stage.level;
    if (levelLessons(lv).every((l) => list.includes(l.key)) && !list.includes(`test:${lv}`))
      router.push(`/academy/test/${lv}?end=1`);
  };

  if (end) {
    const lc = count(levelLessons(stage.level), done ?? []);
    return (
      <main className="page">
        <PageHeader title={lesson.title} back="/academy" />
        <section className="section ta-center">
          <div className="ac-badge" aria-hidden="true">
            ✓
          </div>
          <h2>{end.stageDone ? t.stageDone(stage.title) : t.lessonDone}</h2>
          <div className="ac-meter ta-left">
            <div className="d-flex jc-between fs-sm">
              <span>{level?.name}</span>
              <b>{t.of(lc.n, lc.total)}</b>
            </div>
            <div className="ac-bar">
              <i style={{ width: `${Math.round((lc.n * 100) / Math.max(1, lc.total))}%` }} />
            </div>
          </div>
          {end.stageDone &&
            !stage.review &&
            (token ? (
              end.points != null && (
                <p className="chip green">{end.points ? t.got(end.points) : t.gotBefore}</p>
              )
            ) : (
              <Link href="/login?next=/academy" className="link">
                {t.loginForPoint}
              </Link>
            ))}
          {lesson.see && (
            <Link href={lesson.see.href} className="btn soft mt-10">
              {lesson.see.label}
            </Link>
          )}
          {lesson.task && (
            <>
              <Link
                href={lesson.task.href}
                className="btn soft mt-10"
                onClick={() => waitTask(lesson.key, lesson.task!.need)}
              >
                {lesson.task.label}
              </Link>
              {/* 11/18: 버튼만 눌러서는 안 셈 — 그 화면에서 실제로 해 보면 저절로 「해 봤어요」 */}
              <p className="sub fs-sm mt-6 mb-0 mx-0">
                {taskDone(lesson.key) ? t.taskOk : t.taskHow}
              </p>
            </>
          )}
          <div className="btn-pair mt-10">
            {next && (
              <Link href={`/academy/${next.key}`} className="btn primary">
                {t.next(next.title)}
              </Link>
            )}
            <Link href="/academy" className={next ? "btn secondary" : "btn primary"}>
              {t.toMap}
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <PageHeader title={lesson.title} back="/academy" />
      <p className="sub fs-sm mt-0 mb-0">
        {level?.name} · {stage.title} · {t.lessonNo(no, stage.lessons.length)}
      </p>
      <div className="ac-dots" aria-label={t.progress(at + 1, total)}>
        {Array.from({ length: total }, (_, i) => (
          <i key={i} className={i <= at ? "on" : ""} />
        ))}
      </div>
      <div
        ref={rail}
        className="ac-rail"
        onScroll={(e) => {
          const el = e.currentTarget;
          setAt(Math.round(el.scrollLeft / Math.max(1, el.clientWidth)));
        }}
      >
        {lesson.cards.map((c) => (
          <article key={c.h} className="ac-card">
            <h2 className="ac-h">{c.h}</h2>
            <p className="ac-b">{c.b}</p>
            {c.eg && <p className="ac-eg">{c.eg}</p>}
          </article>
        ))}
        {quizzes.map((qz, n) => {
          const pick = picks[n] ?? null;
          return (
            <article key={qz.q} className="ac-card">
              <p className="sub m-0">{t.quiz(n + 1, quizzes.length)}</p>
              <h2 className="ac-q">{qz.q}</h2>
              {qz.options.map((o, i) => (
                <button
                  key={o}
                  className={`ac-opt${pick === null ? "" : i === qz.answer ? " right" : i === pick ? " wrong" : ""}`}
                  disabled={pick !== null}
                  onClick={() => setPicks((p) => ({ ...p, [n]: i }))}
                >
                  {o}
                </button>
              ))}
              {pick !== null && (
                <p className="ac-b mt-10">
                  <b>{pick === qz.answer ? t.right : t.wrong}</b> {qz.why}
                </p>
              )}
            </article>
          );
        })}
      </div>
      <div className="btn-pair mt-10">
        <button className="btn secondary" disabled={at === 0} onClick={() => go(at - 1)}>
          {t.prev}
        </button>
        {at < total - 1 ? (
          <button className="btn primary" onClick={() => go(at + 1)}>
            {t.nextCard}
          </button>
        ) : (
          <button className="btn primary" disabled={!answered} onClick={finish}>
            {t.finish}
          </button>
        )}
      </div>
    </main>
  );
}
