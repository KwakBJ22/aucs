"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ItemCard } from "@/components/item-card";
import { fetchItems, type ItemList } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile, type Profile } from "@/lib/profile";

const t = copy.home;

export default function Home() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [mine, setMine] = useState<ItemList | null>(null);

  useEffect(() => {
    const p = loadProfile();
    if (!p) {
      router.replace("/start");
      return;
    }
    setProfile(p);
    fetchItems({ sigungu: p.regions, maxCash: p.cash, limit: 20 })
      .then(setMine)
      .catch(() => setMine({ total: 0, items: [] }));
  }, [router]);

  if (!profile) return null;
  const closing = (mine?.items ?? []).filter((c) => c.d_day != null && c.d_day <= 7).slice(0, 2);
  const summary = [
    profile.regions.join("·"),
    profile.cash ? `현금 ${won(profile.cash)}` : null,
    profile.purpose ? t.purposeName[profile.purpose] : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{copy.appName}</div>
        <Link href="/login" style={{ fontSize: 14, fontWeight: 600 }}>
          {t.login}
        </Link>
      </div>
      <Link
        href="/login"
        style={{
          display: "flex",
          justifyContent: "space-between",
          background: "var(--blue-soft)",
          borderRadius: 14,
          padding: "12px 14px",
          color: "var(--blue-text)",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        <span>{t.loginBanner}</span>
        <span aria-hidden="true">›</span>
      </Link>

      {closing.length > 0 && (
        <section className="section">
          <h2 style={{ marginBottom: 12 }}>{t.closing}</h2>
          <div
            style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}
          >
            {closing.map((c) => (
              <div
                key={c.item_id}
                style={{ border: "1px solid var(--line)", borderRadius: 14, padding: 12 }}
              >
                <div style={{ fontSize: 12, fontWeight: 700, color: "var(--red)" }}>
                  {dday(c.d_day)} · {c.sale_date?.slice(5).replace("-", "/")}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 6 }}>{c.place}</div>
                <div
                  className="sub"
                  style={{
                    fontSize: 12,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {c.building ?? c.usage}
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 8 }}>
                  {won(c.min_price_krw)}
                </div>
                <div className="sub" style={{ fontSize: 12 }}>
                  {copy.card.ofAppraisal} {c.min_rate}%
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h2>
            {t.forMe} <span style={{ color: "var(--blue)" }}>{mine?.total ?? ""}</span>
          </h2>
          <Link href="/start" className="sub">
            {t.changeAnswers}
          </Link>
        </div>
        <div className="sub" style={{ marginBottom: 4 }}>
          {summary}
        </div>
        {mine && mine.items.length === 0 && <p className="sub">{t.empty}</p>}
        {mine?.items.slice(0, 5).map((c) => (
          <ItemCard key={c.item_id} c={c} />
        ))}
        {mine && mine.total > 5 && (
          <Link
            href="/find"
            style={{
              display: "block",
              textAlign: "center",
              padding: "12px 0 0",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {copy.find.total(mine.total)} 모두 보기 ›
          </Link>
        )}
      </section>

      <section className="section">
        <h2 style={{ marginBottom: 8 }}>{t.whyTitle}</h2>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            fontSize: 14,
            lineHeight: 1.45,
          }}
        >
          {t.why.map(([a, b]) => (
            <div key={a}>
              <b>{a}</b> · {b}
            </div>
          ))}
        </div>
      </section>
      <Link href="/login" className="btn kakao">
        {t.kakao}
      </Link>
    </main>
  );
}
