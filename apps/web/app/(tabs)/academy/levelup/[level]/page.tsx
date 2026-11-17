"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LEVELS, type Level } from "@/lib/academy.ko";
import { doneLessons, levelLessons, taskCount } from "@/lib/academy";
import { TITLES, XP, reached, streak, xpOf } from "@/lib/academy-game";
import { copy } from "@/lib/copy.ko";

const t = copy.academy;

// 레벨 달성 축하(11/18 대표님 — 레벨마다 축하 화면 하나씩, 게임 레벨업처럼). 시험을 처음 통과하면 이 화면으로 옴.
export default function LevelUp() {
  const { level } = useParams<{ level: string }>();
  const i = LEVELS.findIndex((x) => x.key === level);
  const lv = LEVELS[i];
  const [done, setDone] = useState<string[] | null>(null);
  const [days, setDays] = useState(0);
  useEffect(() => {
    setDone(doneLessons());
    setDays(streak());
  }, []);
  if (!lv || !done) return <main className="page" />;
  if (!done.includes(`test:${lv.key}`))
    return (
      <main className="page">
        <PageHeader title={t.title} back="/academy" />
        <section className="section ta-center">
          <h2>{t.lockedTitle}</h2>
          <Link href={`/academy/test/${lv.key}`} className="btn primary mt-10">
            {t.testGo(lv.name)}
          </Link>
        </section>
      </main>
    );

  const me = TITLES[lv.key as Level];
  const next = LEVELS[i + 1];
  const nextFirst = next ? levelLessons(next.key)[0] : undefined;
  const tasks = taskCount(done);
  return (
    <main className="page">
      <PageHeader title={t.title} back="/academy" />
      <section className="section ta-center ac-hero ac-up">
        <div className="ac-confetti" aria-hidden="true">
          {Array.from({ length: 18 }, (_, n) => (
            <i key={n} />
          ))}
        </div>
        <p className="sub m-0">{t.upKicker}</p>
        <div className="ac-lvbadge big" aria-hidden="true">
          {me.badge}
        </div>
        <h1 className="ac-up-h">{t.upTitle(lv.name)}</h1>
        <p className="fs-lg fw-7 m-0">{t.upNamed(me.title)}</p>
        <p className="sub">{lv.goal}</p>
        <div className="ac-stats">
          <div>
            <b>{xpOf(done).toLocaleString("ko-KR")}</b>
            <span className="sub">{t.statXp}</span>
          </div>
          <div>
            <b>+{XP.test}</b>
            <span className="sub">{t.statThis}</span>
          </div>
          <div>
            <b>{days}</b>
            <span className="sub">{t.statDays}</span>
          </div>
        </div>
        <p className="sub fs-sm">
          {t.upSummary(reached(done), LEVELS.length, tasks.n, tasks.total)}
        </p>
      </section>
      {next ? (
        <section className="section">
          <p className="sub m-0">{t.upNext}</p>
          <h2 className="mt-4">
            {TITLES[next.key as Level].badge} {next.name} · {next.title}
          </h2>
          <p className="sub mt-0">{next.goal}</p>
          {nextFirst && (
            <Link href={`/academy/${nextFirst.key}`} className="btn primary mt-10">
              {t.upGo(next.name)}
            </Link>
          )}
          <Link href="/academy" className="btn secondary mt-8">
            {t.toMap}
          </Link>
        </section>
      ) : (
        <section className="section ta-center">
          <h2 className="m-0">{t.upGrad}</h2>
          <p className="sub">{t.upGradSub}</p>
          <Link href="/find" className="btn primary mt-10">
            {t.upGradGo}
          </Link>
        </section>
      )}
    </main>
  );
}
