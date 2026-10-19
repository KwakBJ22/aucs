"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ItemCard } from "@/components/item-card";
import { fetchItems, type ItemList } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile, type Profile } from "@/lib/profile";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { subscribePush } from "@/lib/push";

const t = copy.home;

export default function Home() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [mine, setMine] = useState<ItemList | null>(null);
  const { session } = useSession();
  const token = session?.access_token ?? null;
  const [alertMsg, setAlertMsg] = useState("");
  const [dropped, setDropped] = useState<Set<string>>(new Set());

  // 비교함에서 이유를 남기고 뺀 물건은 맞춤 목록에서 숨김
  useEffect(() => {
    if (token)
      meApi
        .compare(token)
        .then((c) => setDropped(new Set(c.excluded.map((e) => e.item_id))))
        .catch(() => {});
  }, [token]);

  // 로그인하면 처음 답한 조건을 계정에 옮겨 둠
  useEffect(() => {
    const p = loadProfile();
    if (token && p)
      meApi
        .saveProfile(token, { regions: p.regions, cash: p.cash, purpose: p.purpose })
        .catch(() => {});
  }, [token]);

  async function turnOnAlert(p: Profile) {
    if (!token) {
      router.push("/login");
      return;
    }
    await meApi.addSearch(token, copy.alert.name, { sigungu: p.regions, max_cash: p.cash });
    const r = await subscribePush(token);
    setAlertMsg(
      r === "ok" ? copy.alert.saved : r === "denied" ? copy.alert.denied : copy.alert.unsupported,
    );
  }

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
  const shown = mine && { ...mine, items: mine.items.filter((c) => !dropped.has(c.item_id)) };
  const closing = (shown?.items ?? []).filter((c) => c.d_day != null && c.d_day <= 7).slice(0, 2);
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
        {token ? (
          <Link
            href="/notifications"
            aria-label={copy.noti.title}
            style={{
              minWidth: 44,
              minHeight: 44,
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
            }}
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7M10 20a2 2 0 0 0 4 0" />
            </svg>
          </Link>
        ) : (
          <Link href="/login" style={{ fontSize: 14, fontWeight: 600 }}>
            {t.login}
          </Link>
        )}
      </div>
      {!token && (
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
      )}

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
        <button
          className="btn"
          style={{
            background: "var(--blue-soft)",
            color: "var(--blue-text)",
            margin: "8px 0 4px",
            height: 44,
            fontSize: 14,
          }}
          onClick={() => void turnOnAlert(profile)}
        >
          {copy.alert.button}
        </button>
        {alertMsg && (
          <p className="sub" style={{ margin: "0 0 4px" }}>
            {alertMsg}
          </p>
        )}
        {shown && shown.items.length === 0 && <p className="sub">{t.empty}</p>}
        {shown?.items.slice(0, 5).map((c) => (
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
      {!token && (
        <Link href="/login" className="btn kakao">
          {t.kakao}
        </Link>
      )}
    </main>
  );
}
