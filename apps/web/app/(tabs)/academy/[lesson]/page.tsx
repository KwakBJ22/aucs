"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LEVELS, findLesson } from "@/lib/academy.ko";
import {
  count,
  doneLessons,
  isOpen,
  lessonAfter,
  levelLessons,
  markLesson,
  nextLesson,
} from "@/lib/academy";
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
  const rail = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState(0);
  const [pick, setPick] = useState<number | null>(null);
  const [end, setEnd] = useState<{ stageDone: boolean; points: number | null } | null>(null);
  const [done, setDone] = useState<string[] | null>(null); // 기기에 적어 둔 진도(읽기 전엔 null)
  useEffect(() => setDone(doneLessons()), []);

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
  const total = lesson.cards.length + 1; // 카드 + 문제
  const no = stage.lessons.findIndex((l) => l.key === lesson.key) + 1;

  if (done && !isOpen(lesson.key, done)) {
    const turn = nextLesson(done);
    return (
      <main className="page">
        <PageHeader title={t.title} back="/academy" />
        <section className="section ta-center">
          <h2>{t.lockedTitle}</h2>
          <p className="sub">{stage.level === "adv" ? t.noteAdv : t.lockedSub}</p>
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
    const list = markLesson(lesson.key);
    setDone(list);
    const stageDone = stage.lessons.every((l) => list.includes(l.key));
    setEnd({ stageDone, points: null });
    if (stageDone && token && !stage.review)
      meApi
        .academyDone(token, stage.key)
        .then((x) => setEnd({ stageDone, points: x.points }))
        .catch(() => undefined);
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
            <Link
              href={lesson.task.href}
              className="btn soft mt-10"
              onClick={() => markLesson(`task:${lesson.key}`)}
            >
              {lesson.task.label}
            </Link>
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
        <article className="ac-card">
          <p className="sub m-0">{t.quiz}</p>
          <h2 className="ac-q">{lesson.quiz.q}</h2>
          {lesson.quiz.options.map((o, i) => (
            <button
              key={o}
              className={`ac-opt${pick === null ? "" : i === lesson.quiz.answer ? " right" : i === pick ? " wrong" : ""}`}
              disabled={pick !== null}
              onClick={() => setPick(i)}
            >
              {o}
            </button>
          ))}
          {pick !== null && (
            <p className="ac-b mt-10">
              <b>{pick === lesson.quiz.answer ? t.right : t.wrong}</b> {lesson.quiz.why}
            </p>
          )}
        </article>
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
          <button className="btn primary" disabled={pick === null} onClick={finish}>
            {t.finish}
          </button>
        )}
      </div>
    </main>
  );
}
