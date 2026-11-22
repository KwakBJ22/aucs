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
  pendingTest,
  stageEntry,
  syncProgress,
  taskCount,
} from "@/lib/academy";
import { TITLES, nextGoal, reached, streak, xpOf } from "@/lib/academy-game";
import { fetchAcademyJudge, fetchAcademyToday, type AcademyToday } from "@/lib/api/items";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { LevelIcon } from "@/components/level-icon";

const t = copy.academy;

// 오늘의 물건 문제(11/17): 실제 물건 · 낙찰 결과로 하루 한 문제 — 정답은 계산으로만 나오는 것.
// 레벨4가 열리면 「실제 물건 판정」(명세서 원문 한 줄 → 떠안나?)도 같은 모양으로 — 로그인 회원만.
function Today({
  load,
  title,
  sub,
}: {
  load: () => Promise<AcademyToday | null>;
  title: string;
  sub: string;
}) {
  const [x, setX] = useState<AcademyToday | null>(null);
  const [pick, setPick] = useState<number | null>(null);
  // 고른 답은 이 기기에 기억(11/18 대표님) — 「이 물건 보기」 갔다 와도 다시 풀라고 하지 않게.
  // 문제 종류마다 한 칸(마지막 문제만) — 새 문제가 오면 덮어씀
  const slot = x ? `aucs_ac_pick:${x.kind}` : "";
  const qid = x ? `${x.item_id ?? ""}|${x.q}` : "";
  useEffect(() => {
    load()
      .then(setX)
      .catch(() => undefined);
  }, [load]);
  useEffect(() => {
    if (!slot) return;
    try {
      const v = JSON.parse(localStorage.getItem(slot) ?? "null") as { q: string; i: number } | null;
      if (v?.q === qid) setPick(v.i);
    } catch {
      /* 기억 못 하는 브라우저 — 그대로 */
    }
  }, [slot, qid]);
  const choose = (i: number) => {
    setPick(i);
    try {
      localStorage.setItem(slot, JSON.stringify({ q: qid, i }));
    } catch {
      /* 그대로 */
    }
  };
  if (!x) return null;
  return (
    <section className="section">
      <div className="d-flex jc-between ai-center gap-8">
        <h2 className="m-0">{title}</h2>
        <span className="sub fs-sm">{sub}</span>
      </div>
      <p className="ac-b ac-q mt-8">{x.q}</p>
      <div className="ac-opts">
        {x.options.map((o, i) => (
          <button
            key={o}
            className={`ac-opt${pick === null ? "" : i === x.answer ? " right" : i === pick ? " wrong" : ""}`}
            disabled={pick !== null}
            onClick={() => choose(i)}
          >
            {o}
          </button>
        ))}
      </div>
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
      <div className="ac-meter-l">
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
  const [days, setDays] = useState(0);

  useEffect(() => {
    setDone(doneLessons());
    setDays(streak());
  }, []);
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
  const test = pendingTest(done); // 수업을 다 들은 레벨의 시험이 먼저(11/18 — 통과해야 레벨업)
  const lvNow = reached(done);
  const me = lvNow ? LEVELS[lvNow - 1] : null;
  const goal = nextGoal(done, levelLessons);
  const lessons = count(
    STAGES.flatMap((s) => s.lessons),
    done,
  );
  const tasks = taskCount(done);
  const l4Open = STAGES.some((s) => s.level === "l4" && stageEntry(s, done));
  return (
    <main className="page">
      <PageHeader title={t.title} back="/home" />
      <p className="sub fs-base mt-0">{t.sub}</p>
      {/* 11/18 대표님: 게임처럼 — 지금 레벨 · 칭호 · 경험치 · 연속 학습 · 다음 레벨까지 */}
      {/* 11/22 디자인: PC 는 왼쪽 지금 레벨(선 그림) · 오른쪽 막대 셋, 아래 주 버튼 */}
      <section className="section ac-hero">
        <div className="ac-hero-grid">
          <div className="d-flex ai-center gap-12 ac-me">
            <div className="ac-lvbadge" aria-hidden="true">
              <LevelIcon level={me ? me.key : null} />
            </div>
            <div className="f-1 minw-0">
              <p className="sub m-0">{me ? t.nowLevel(me.name) : t.nowNone}</p>
              <h2 className="m-0">{me ? TITLES[me.key].title : t.nowNoneTitle}</h2>
              <p className="sub fs-sm m-0">
                {t.xpLine(xpOf(done))}
                {days > 0 && ` · ${t.streakLine(days)}`}
              </p>
            </div>
          </div>
          <div className="ac-meters">
            {goal && <Meter label={t.goalLine(goal.level.name)} n={goal.have} total={goal.total} />}
            <Meter label={t.meterLesson} n={lessons.n} total={lessons.total} />
            <Meter label={t.meterTask} n={tasks.n} total={tasks.total} />
          </div>
        </div>
        {test ? (
          <Link href={`/academy/test/${test}`} className="btn primary mt-12">
            {t.testUp(LEVELS.find((x) => x.key === test)?.name ?? "")}
          </Link>
        ) : next ? (
          <Link href={`/academy/${next.key}`} className="btn primary mt-12">
            {done.length ? t.resume(next.title) : t.start}
          </Link>
        ) : (
          <p className="chip green mt-12">{t.allDone}</p>
        )}
      </section>

      <Today load={fetchAcademyToday} title={t.today} sub={t.todaySub} />
      {token && l4Open && <Today load={fetchAcademyJudge} title={t.judge} sub={t.judgeSub} />}

      {LEVELS.map((lv) => {
        const stages = STAGES.filter((s) => s.level === lv.key);
        const c = count(levelLessons(lv.key), done);
        const prev = LEVELS[LEVELS.indexOf(lv) - 1];
        const prevDone =
          !prev ||
          SKIPPABLE.includes(prev.key) ||
          (levelLessons(prev.key).every((l) => done.includes(l.key)) &&
            done.includes(`test:${prev.key}`));
        const note =
          lv.key === "l1" ? t.noteBasic : !prevDone ? t.noteLevel(prev?.name ?? "") : null;
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
                  <span>{c.n === c.total ? t.testUp(lv.name) : t.testSkip}</span>
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
