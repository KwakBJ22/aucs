"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LEVELS, STAGES, TESTS } from "@/lib/academy.ko";
import {
  SKIPPABLE,
  count,
  doneLessons,
  levelLessons,
  nextLesson,
  stageEntry,
  syncProgress,
  taskCount,
} from "@/lib/academy";
import { fetchAcademyToday, type AcademyToday } from "@/lib/api/items";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.academy;

// 오늘의 물건 문제(11/17): 실제 물건 · 낙찰 결과로 하루 한 문제 — 정답은 계산으로만 나오는 것
function Today() {
  const [x, setX] = useState<AcademyToday | null>(null);
  const [pick, setPick] = useState<number | null>(null);
  useEffect(() => {
    fetchAcademyToday()
      .then(setX)
      .catch(() => undefined);
  }, []);
  if (!x) return null;
  return (
    <section className="section">
      <div className="d-flex jc-between ai-center gap-8">
        <h2 className="m-0">{t.today}</h2>
        <span className="sub fs-sm">{t.todaySub}</span>
      </div>
      <p className="ac-b mt-8">{x.q}</p>
      {x.options.map((o, i) => (
        <button
          key={o}
          className={`ac-opt${pick === null ? "" : i === x.answer ? " right" : i === pick ? " wrong" : ""}`}
          disabled={pick !== null}
          onClick={() => setPick(i)}
        >
          {o}
        </button>
      ))}
      {pick !== null && (
        <p className="ac-b mt-10">
          <b>{pick === x.answer ? t.right : t.wrong}</b> {x.why}{" "}
          {x.item_id && (
            <Link href={`/item/${encodeURIComponent(x.item_id)}`} className="link">
              {t.todayItem}
            </Link>
          )}
        </p>
      )}
    </section>
  );
}

function Meter({ label, n, total }: { label: string; n: number; total: number }) {
  return (
    <div className="ac-meter">
      <div className="d-flex jc-between fs-sm">
        <span>{label}</span>
        <b>{t.of(n, total)}</b>
      </div>
      <div className="ac-bar">
        <i style={{ width: `${total ? Math.round((n * 100) / total) : 0}%` }} />
      </div>
    </div>
  );
}

// 옥스아카데미(11/14 · 11/17 대표님): 목차(레벨 1~7 → 단계)만 보이는 커리큘럼 한 장. 수업은 차례대로만 열림 —
// 레벨 1 · 2 는 건너뛰어도 되고, 레벨 4부터는 앞 레벨을 다 들어야 열림. 위에 수업 진도 · 옥스 활용(과제) 두 줄.
export default function Academy() {
  const { session } = useSession();
  const token = session?.access_token;
  const [done, setDone] = useState<string[]>([]);
  const [paid, setPaid] = useState<string[]>([]);

  useEffect(() => setDone(doneLessons()), []);
  useEffect(() => {
    if (!token) return;
    let stop = false;
    syncProgress(token) // 계정 진도와 합침 — 다른 기기에서 들은 것도 이어짐
      .then((x) => {
        if (stop) return;
        setPaid(x.stages);
        setDone(x.done);
      })
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, [token]);

  const next = nextLesson(done);
  const lessons = count(
    STAGES.flatMap((s) => s.lessons),
    done,
  );
  const tasks = taskCount(done);
  return (
    <main className="page">
      <PageHeader title={t.title} back="/home" />
      <p className="sub fs-base mt-0">{t.sub}</p>
      <section className="section">
        <Meter label={t.meterLesson} n={lessons.n} total={lessons.total} />
        <Meter label={t.meterTask} n={tasks.n} total={tasks.total} />
        {next ? (
          <Link href={`/academy/${next.key}`} className="btn primary mt-12">
            {done.length ? t.resume(next.title) : t.start}
          </Link>
        ) : (
          <p className="chip green mt-12">{t.allDone}</p>
        )}
      </section>

      <Today />

      {LEVELS.map((lv) => {
        const stages = STAGES.filter((s) => s.level === lv.key);
        const c = count(levelLessons(lv.key), done);
        const prev = LEVELS[LEVELS.indexOf(lv) - 1];
        const prevDone = !prev || levelLessons(prev.key).every((l) => done.includes(l.key));
        const note =
          lv.key === "l1"
            ? t.noteBasic
            : lv.key === "l7"
              ? prevDone
                ? t.reviewNote
                : t.noteLevel(prev?.name ?? "")
              : null;
        return (
          <section key={lv.key} className="section ac-level">
            <div className="d-flex jc-between ai-center gap-8">
              <h2 className="m-0">
                <span className="chip blue">{lv.name}</span> {lv.title}
              </h2>
              <span className="sub fs-sm">{t.of(c.n, c.total)}</span>
            </div>
            {note && <p className="sub fs-sm mt-4 mb-0">{note}</p>}
            {stages.map((s, i) => {
              const sc = count(s.lessons, done);
              const full = sc.n === sc.total;
              const go = stageEntry(s, done);
              const row = (
                <>
                  <span>
                    <span className={`ac-step${full ? " on" : ""}`}>{i + 1}</span> {s.title}
                  </span>
                  <span className="sub">
                    {paid.includes(s.key) && <span className="chip green">{t.paid}</span>}{" "}
                    {go ? `${t.of(sc.n, sc.total)} ›` : t.locked}
                  </span>
                </>
              );
              return go ? (
                <Link key={s.key} href={`/academy/${go.key}`} className="menu-row">
                  {row}
                </Link>
              ) : (
                <div key={s.key} className="menu-row ac-locked" aria-disabled="true">
                  {row}
                </div>
              );
            })}
            {TESTS[lv.key] &&
              (c.n === c.total || SKIPPABLE.includes(lv.key)) &&
              (done.includes(`test:${lv.key}`) ? (
                <Link href={`/academy/test/${lv.key}`} className="menu-row">
                  <span>{t.test}</span>
                  <span className="chip green">{t.passed}</span>
                </Link>
              ) : (
                <Link href={`/academy/test/${lv.key}`} className="menu-row">
                  <span>{c.n === c.total ? t.testGo(lv.name) : t.testSkip}</span>
                  <span className="sub">›</span>
                </Link>
              ))}
          </section>
        );
      })}
      {!token && done.length > 0 && (
        <Link href="/login?next=/academy" className="link fs-sm mt-12 d-inline-block">
          {t.loginForPoint}
        </Link>
      )}
    </main>
  );
}
