"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AskBox } from "@/components/ask-box";
import { PageHeader } from "@/components/layout/page-header";
import { fetchNotices, type PublicNotice } from "@/lib/api/items";
import { meApi, type MyInquiry } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.help;

// 고객센터(11/7): 공지 · 문의하기 · 자주 묻는 질문 · 약관과 정책. 전화번호는 사업자등록 뒤.
export default function HelpPage() {
  const { session } = useSession();
  const [notices, setNotices] = useState<PublicNotice[] | null>(null);
  const [asks, setAsks] = useState<MyInquiry[]>([]);
  useEffect(() => {
    fetchNotices()
      .then(setNotices)
      .catch(() => setNotices([]));
  }, []);
  useEffect(() => {
    if (!session) return;
    meApi
      .inquiries(session.access_token)
      .then(setAsks)
      .catch(() => {});
  }, [session]);

  return (
    <main className="page narrow">
      <PageHeader title={t.title} />
      <p className="sub mt-0">{t.hours}</p>

      <section className="section" id="notice">
        <h2>{t.noticeTitle}</h2>
        {notices?.length === 0 && <p className="sub">{t.noticeNone}</p>}
        {notices?.map((n) => (
          <details key={n.notice_id} className="faq">
            <summary>
              <span>{n.title}</span>
              <span className="sub fs-xs">{n.start_at.slice(0, 10)}</span>
            </summary>
            <p>{n.body}</p>
          </details>
        ))}
      </section>

      {session ? (
        <AskBox token={session.access_token} initial={asks} />
      ) : (
        <section className="section" id="ask">
          <h2>{copy.ask.title}</h2>
          <p className="sub">{t.askLogin}</p>
          <Link href="/login" className="btn soft mt-8">
            {t.login}
          </Link>
        </section>
      )}

      <section className="section" id="faq">
        <h2>{t.faqTitle}</h2>
        {t.faq.map(([q, a]) => (
          <details key={q} className="faq">
            <summary>
              <span>{q}</span>
            </summary>
            <p>{a}</p>
          </details>
        ))}
      </section>

      <section className="section py-4 px-18" id="docs">
        {t.docs.map(([name, href]) => (
          <Link key={href} href={href} className="menu-row">
            <span>{name}</span>
            <span className="sub">›</span>
          </Link>
        ))}
      </section>
    </main>
  );
}
