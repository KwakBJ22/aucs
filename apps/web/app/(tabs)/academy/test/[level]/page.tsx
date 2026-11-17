"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LEVELS, TESTS, TEST_PASS, findLesson, type Level } from "@/lib/academy.ko";
import { SKIPPABLE, doneLessons, levelLessons, mark } from "@/lib/academy";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.academy;

// 레벨 시험(11/17 대표님): 5문제 · 4개 맞으면 통과 · 떨어져도 바로 다시. 틀린 문제는 나온 수업을 짚어 줌.
// 레벨 1 · 2 는 수업 전에 봐도 되고(아는 분 건너뛰기), 그 위 레벨은 수업을 다 들은 뒤에 봄.
export default function LevelTest() {
  const { level } = useParams<{ level: string }>();
  const lv = LEVELS.find((x) => x.key === level);
  const qs = lv ? TESTS[lv.key as Level] : undefined;
  const { session } = useSession();
  const [done, setDone] = useState<string[] | null>(null);
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [graded, setGraded] = useState(false);
  useEffect(() => setDone(doneLessons()), []);

  if (!lv || !qs?.length)
    return (
      <main className="page">
        <PageHeader title={t.test} back="/academy" />
        <p className="sub">{t.testNone}</p>
      </main>
    );
  const open =
    SKIPPABLE.includes(lv.key) || levelLessons(lv.key).every((l) => (done ?? []).includes(l.key));
  if (done && !open)
    return (
      <main className="page">
        <PageHeader title={t.test} back="/academy" />
        <section className="section ta-center">
          <h2>{t.lockedTitle}</h2>
          <p className="sub">{t.lockedSub}</p>
        </section>
      </main>
    );

  const right = qs.filter((q, i) => picks[i] === q.answer).length;
  const pass = right >= TEST_PASS;
  const grade = () => {
    setGraded(true);
    if (right >= TEST_PASS) setDone(mark(`test:${lv.key}`, session?.access_token));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const again = () => {
    setPicks({});
    setGraded(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <main className="page">
      <PageHeader title={`${lv.name} ${t.test}`} back="/academy" />
      {graded ? (
        <section className="section ta-center">
          <div className="ac-badge" aria-hidden="true">
            {pass ? "✓" : t.testScore(right, qs.length)}
          </div>
          <h2>{pass ? t.testPass(lv.name) : t.testFail(right, qs.length)}</h2>
          {!pass && <p className="sub">{t.testFailSub}</p>}
          {!pass &&
            qs.map((q, i) => {
              if (picks[i] === q.answer) return null;
              const f = q.from ? findLesson(q.from) : null;
              return (
                <div key={q.q} className="ta-left mt-10">
                  <p className="ac-b m-0">
                    <b>{q.q}</b> {q.why}
                  </p>
                  {f && (
                    <Link href={`/academy/${f.lesson.key}`} className="link fs-sm">
                      {t.testFrom(f.lesson.title)}
                    </Link>
                  )}
                </div>
              );
            })}
          <div className="btn-pair mt-10">
            {!pass && (
              <button className="btn primary" onClick={again}>
                {t.testAgain}
              </button>
            )}
            <Link href="/academy" className={pass ? "btn primary" : "btn secondary"}>
              {t.toMap}
            </Link>
          </div>
        </section>
      ) : (
        <>
          <p className="sub fs-sm mt-0">{t.testSub(qs.length, TEST_PASS)}</p>
          {qs.map((q, n) => (
            <section key={q.q} className="section">
              <p className="sub m-0">{t.quiz(n + 1, qs.length)}</p>
              <h2 className="ac-q">{q.q}</h2>
              {q.options.map((o, i) => (
                <button
                  key={o}
                  className={`ac-opt${picks[n] === i ? " right" : ""}`}
                  onClick={() => setPicks((p) => ({ ...p, [n]: i }))}
                >
                  {o}
                </button>
              ))}
            </section>
          ))}
          <button
            className="btn primary mt-10"
            disabled={qs.some((_, i) => picks[i] === undefined)}
            onClick={grade}
          >
            {t.testSubmit}
          </button>
        </>
      )}
    </main>
  );
}
