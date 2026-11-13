"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { LEVELS, STAGES } from "@/lib/academy.ko";
import { doneLessons } from "@/lib/academy";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.academy;

// 경매 아카데미(11/14 대표님): 단계가 길처럼 이어진 한 장 — 내 진도 · 「이어서 듣기」 하나
export default function Academy() {
  const { session } = useSession();
  const token = session?.access_token;
  const [done, setDone] = useState<string[]>([]);
  const [paid, setPaid] = useState<string[]>([]);

  useEffect(() => setDone(doneLessons()), []);
  useEffect(() => {
    if (!token) return;
    let stop = false;
    meApi
      .academy(token)
      .then((x) => !stop && setPaid(x.stages))
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, [token]);

  const all = STAGES.flatMap((s) => s.lessons);
  const next = all.find((l) => !done.includes(l.key));
  return (
    <main className="page">
      <PageHeader title={t.title} back="/home" />
      <p className="sub fs-base mt-0">{t.sub}</p>
      {next ? (
        <Link href={`/academy/${next.key}`} className="btn primary mt-10">
          {done.length ? t.resume(next.title) : t.start}
        </Link>
      ) : (
        <p className="chip green mt-10">{t.allDone}</p>
      )}

      {LEVELS.map((lv) => {
        const stages = STAGES.filter((s) => s.level === lv.key);
        const open = stages.some((s) => s.lessons.length > 0);
        return (
          <div key={lv.key} className="ac-level">
            <div className="d-flex ai-center gap-8">
              <span className={`chip ${open ? "blue" : "gray"}`}>{lv.name}</span>
              <b className="fs-lg">{lv.title}</b>
            </div>
            <p className="sub fs-sm mt-4 mb-0">{lv.goal}</p>
            {!open && (
              <section className="section">
                <p className="m-0">{stages.map((s) => s.title).join(" · ")}</p>
                <p className="sub fs-sm mt-6 mb-0">{t.soon}</p>
              </section>
            )}
            {open &&
              stages.map((s, i) => (
                <section key={s.key} className="section ac-stage">
                  <div className="d-flex jc-between ai-center gap-8">
                    <h2 className="m-0">
                      <span className="ac-step">{i + 1}</span> {s.title}
                    </h2>
                    <span className={`chip ${paid.includes(s.key) ? "green" : "blue"}`}>
                      {paid.includes(s.key) ? t.paid : t.reward}
                    </span>
                  </div>
                  <p className="sub fs-sm mt-4">{s.goal}</p>
                  {s.lessons.map((l) => (
                    <Link key={l.key} href={`/academy/${l.key}`} className="menu-row">
                      <span>
                        <span
                          className={`ac-check${done.includes(l.key) ? " on" : ""}`}
                          aria-hidden="true"
                        />
                        {l.title}
                      </span>
                      <span className="sub">{done.includes(l.key) ? t.again : t.min} ›</span>
                    </Link>
                  ))}
                  {!token &&
                    s.lessons.every((l) => done.includes(l.key)) &&
                    !paid.includes(s.key) && (
                      <Link href="/login?next=/academy" className="link fs-sm mt-6 d-inline-block">
                        {t.loginForPoint}
                      </Link>
                    )}
                </section>
              ))}
          </div>
        );
      })}
    </main>
  );
}
