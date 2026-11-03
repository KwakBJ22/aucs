"use client";

import { SkListPage } from "@/components/skeleton";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AskBox } from "@/components/ask-box";
import { LeaveBox } from "@/components/leave-box";
import { PageHeader } from "@/components/layout/page-header";
import { meApi, type MyInquiry, type SavedSearch } from "@/lib/api/me";
import { signOut, useSession } from "@/lib/auth";
import { condSummary } from "@/lib/cond";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { loadProfile, type Profile } from "@/lib/profile";
import { useIsPc } from "@/lib/use-pc";

const t = copy.more;

// 전체(내 정보, MENU-01·02 · PC-ME). PC는 왼쪽 목록 20 · 오른쪽 내용 80.
export default function More() {
  const { session, ready } = useSession();
  const pc = useIsPc();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  useEffect(() => setProfile(loadProfile()), []);
  const [inquiries, setInquiries] = useState<MyInquiry[]>([]);
  useEffect(() => {
    // 알림 조건·문의를 한 번에(11/3 — 예전 2번)
    if (session)
      meApi
        .more(session.access_token)
        .then((m) => {
          setSearches(m.searches);
          setInquiries(m.inquiries);
        })
        .catch(() => {});
  }, [session]);
  if (!ready)
    return (
      <main className="page">
        <SkListPage cards={false} n={8} />
      </main>
    );

  const head = (
    <section className="section" id="me">
      {session ? (
        <>
          <h2>{t.hello}</h2>
          <div className="sub">{session.user.email}</div>
          <Link href="/more/billing" className="menu-row mt-8">
            <span>{t.plan}</span>
            <span className="sub">›</span>
          </Link>
        </>
      ) : (
        <>
          <h2>{t.title}</h2>
          <div className="sub fs-md">{t.sub}</div>
          <Link href="/login" className="btn kakao mt-14">
            {copy.home.kakao}
          </Link>
        </>
      )}
    </section>
  );
  const cond = (
    <section className="section" id="cond">
      <h2>{t.cond}</h2>
      {profile ? (
        <>
          <div className="line-row">
            <span className="sub">{t.regions}</span>
            <span>{profile.regions.join(" · ") || "-"}</span>
          </div>
          <div className="line-row">
            <span className="sub">{t.cash}</span>
            <span>{profile.cash ? won(profile.cash) : "-"}</span>
          </div>
          <div className="line-row">
            <span className="sub">{t.purpose}</span>
            <span>{profile.purpose ? copy.home.purposeName[profile.purpose] : "-"}</span>
          </div>
          <div className="line-row">
            <span className="sub">{t.homes}</span>
            <span>{profile.homes != null ? t.homesN(profile.homes) : "-"}</span>
          </div>
        </>
      ) : (
        <p className="sub">{t.condNone}</p>
      )}
      <Link href="/start" className="menu-row">
        <span>{copy.home.changeAnswers}</span>
        <span />
      </Link>
    </section>
  );
  const alerts = session && (
    <section className="section" id="alerts">
      <h2>{t.alerts}</h2>
      {searches.length === 0 && <p className="sub">{t.alertsNone}</p>}
      {searches.map((x) => (
        <div key={x.search_id} className="line-row fs-md">
          <span className="minw-0">
            {condSummary(x.filters)}
            <span className="sub d-block fs-xs">
              {x.delivery === "instant" ? t.instant : t.daily}
            </span>
          </span>
          {session && (
            <button
              className="link-btn"
              onClick={() =>
                void meApi
                  .removeSearch(session.access_token, x.search_id)
                  .then(() => setSearches((s) => s.filter((y) => y.search_id !== x.search_id)))
                  .catch(() => {})
              }
            >
              {t.alertDel}
            </button>
          )}
        </div>
      ))}
      <Link href="/find" className="menu-row">
        <span>{t.alertsAdd}</span>
        <span className="sub">›</span>
      </Link>
    </section>
  );
  const menu = (
    <section className="section py-4 px-18" id="menu">
      {t.items.map(([name, href]) =>
        href ? (
          <Link key={name} href={href} className="menu-row">
            <span>{name}</span>
            <span className="sub">›</span>
          </Link>
        ) : (
          <div key={name} className="menu-row">
            <span>{name}</span>
            <span className="sub">{t.soon}</span>
          </div>
        ),
      )}
      {session && (
        <>
          <button className="menu-row w-full b-0 bg-none ta-left" onClick={() => void signOut()}>
            <span>{t.logout}</span>
            <span />
          </button>
          <LeaveBox token={session.access_token} />
        </>
      )}
    </section>
  );

  if (pc)
    return (
      <main className="page">
        <PageHeader title={t.pcTitle} />
        <div className="pc-grid g-20-80">
          <nav className="section toc pc-sticky mt-0">
            {t.toc.map(([label, href]) => (
              <a key={href} href={href}>
                {label}
              </a>
            ))}
          </nav>
          <div className="pc-grid g-2x2">
            <div>
              {head}
              {cond}
            </div>
            <div>
              {alerts}
              {menu}
              {session && <AskBox token={session.access_token} initial={inquiries} />}
            </div>
          </div>
        </div>
      </main>
    );
  return (
    <main className="page">
      <PageHeader title={t.title} />
      {head}
      {cond}
      {alerts}
      {menu}
      {session && <AskBox token={session.access_token} initial={inquiries} />}
    </main>
  );
}
