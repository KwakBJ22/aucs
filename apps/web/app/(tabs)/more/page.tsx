"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { meApi, type SavedSearch } from "@/lib/api/me";
import { signOut, useSession } from "@/lib/auth";
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
  useEffect(() => {
    if (session) meApi.searches(session.access_token).then(setSearches).catch(() => {});
  }, [session]);
  if (!ready) return null;

  const head = (
    <section className="section" id="me">
      {session ? (
        <>
          <h2>{t.hello}</h2>
          <div className="sub">{session.user.email}</div>
          <div className="chip gray" style={{ marginTop: 8 }}>{t.plan}</div>
        </>
      ) : (
        <>
          <h2>{t.title}</h2>
          <div className="sub" style={{ fontSize: 14 }}>{t.sub}</div>
          <Link href="/login" className="btn kakao" style={{ marginTop: 14 }}>
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
          <div className="line-row"><span className="sub">{t.regions}</span><span>{profile.regions.join(" · ") || "-"}</span></div>
          <div className="line-row"><span className="sub">{t.cash}</span><span>{profile.cash ? won(profile.cash) : "-"}</span></div>
          <div className="line-row"><span className="sub">{t.purpose}</span><span>{profile.purpose ? copy.home.purposeName[profile.purpose] : "-"}</span></div>
          <div className="line-row"><span className="sub">{t.homes}</span><span>{profile.homes != null ? t.homesN(profile.homes) : "-"}</span></div>
        </>
      ) : (
        <p className="sub">{t.condNone}</p>
      )}
      <Link href="/start" className="menu-row"><span>{copy.home.changeAnswers}</span><span /></Link>
    </section>
  );
  const alerts = session && (
    <section className="section" id="alerts">
      <h2>{t.alerts}</h2>
      {searches.length === 0 && <p className="sub">{t.alertsNone}</p>}
      {searches.map((x) => (
        <div key={x.search_id} className="line-row" style={{ fontSize: 14 }}>
          <span>{x.name}</span>
          <span className="sub">{x.delivery === "instant" ? t.instant : t.daily}</span>
        </div>
      ))}
      <Link href="/find" className="menu-row"><span>{t.alertsAdd}</span><span className="sub">›</span></Link>
    </section>
  );
  const menu = (
    <section className="section" id="menu" style={{ padding: "4px 18px" }}>
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
        <button className="menu-row" style={{ width: "100%", border: 0, background: "none", textAlign: "left" }} onClick={() => void signOut()}>
          <span>{t.logout}</span>
          <span />
        </button>
      )}
    </section>
  );

  if (pc)
    return (
      <main className="page">
        <PageHeader title={t.pcTitle} />
        <div className="pc-grid g-20-80">
          <nav className="section toc pc-sticky" style={{ marginTop: 0 }}>
            {t.toc.map(([label, href]) => (
              <a key={href} href={href}>{label}</a>
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
    </main>
  );
}
