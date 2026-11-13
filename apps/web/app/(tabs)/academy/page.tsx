"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { STAGES } from "@/lib/academy.ko";
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

      {STAGES.map((s, i) => {
        const n = s.lessons.filter((l) => done.includes(l.key)).length;
        const complete = s.lessons.length > 0 && n === s.lessons.length;
        return (
          <section key={s.key} className="section ac-stage">
            <div className="d-flex jc-between ai-center gap-8">
              <h2 className="m-0">
                <span className="ac-step">{i}</span> {s.title}
              </h2>
              {s.lessons.length === 0 ? (
                <span className="chip gray">{t.soon}</span>
              ) : paid.includes(s.key) ? (
                <span className="chip green">{t.paid}</span>
              ) : (
                <span className="chip blue">{t.reward}</span>
              )}
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
            {s.soon && <p className="sub fs-sm mt-6 mb-0">{s.soon.join(" · ")}</p>}
            {complete && !paid.includes(s.key) && !token && (
              <Link href="/login?next=/academy" className="link fs-sm mt-6 d-inline-block">
                {t.loginForPoint}
              </Link>
            )}
          </section>
        );
      })}
    </main>
  );
}
