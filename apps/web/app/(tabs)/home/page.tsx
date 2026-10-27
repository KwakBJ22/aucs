"use client";

import { LoadError } from "@/components/load-error";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ItemCard } from "@/components/item-card";
import { fetchItems, type ItemList } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile, type Profile } from "@/lib/profile";
import { meApi, type Noti, type WatchCard } from "@/lib/api/me";
import { fetchMarket, type Market } from "@/lib/api/pro";
import { PageHeader } from "@/components/layout/page-header";
import { useIsPc } from "@/lib/use-pc";
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
  const [watch, setWatch] = useState<WatchCard[]>([]);
  const [notis, setNotis] = useState<Noti[]>([]);
  const [market, setMarket] = useState<Market | null>(null);
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);
  const pc = useIsPc();

  // 내 물건 변화·오늘 할 일·비교함에서 뺀 물건(맞춤 목록에서 숨김)을 한 번에
  useEffect(() => {
    if (!token) return;
    meApi
      .home(token)
      .then((h) => {
        setWatch(h.watch);
        setNotis(h.notifications);
        setDropped(new Set(h.excluded));
      })
      .catch(() => {});
  }, [token]);
  // PC 오른쪽: 이번 석 달 법원별 낙찰가율
  useEffect(() => {
    if (pc && !market)
      fetchMarket({ months: 3 })
        .then(setMarket)
        .catch(() => {});
  }, [pc, market]);

  // 로그인하면 처음 답한 조건을 계정에 옮겨 둠
  useEffect(() => {
    const p = loadProfile();
    if (!token || !p) return;
    const body = { regions: p.regions, cash: p.cash, purpose: p.purpose };
    const sig = JSON.stringify(body);
    let last: string | null = null;
    try {
      last = localStorage.getItem("aucs_profile_sent");
    } catch {}
    if (last === sig) return; // 바뀐 게 없으면 다시 보내지 않음
    meApi
      .saveProfile(token, body)
      .then(() => {
        try {
          localStorage.setItem("aucs_profile_sent", sig);
        } catch {}
      })
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
    setFailed(false);
    fetchItems({ sigungu: p.regions, maxCash: p.cash, limit: 20 })
      .then(setMine)
      .catch(() => setFailed(true));
  }, [router, tries]);

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

  const todo = watch
    .filter(
      (w) =>
        w.d_day != null &&
        w.d_day >= 0 &&
        w.d_day <= 7 &&
        w.step !== "result" &&
        w.step !== "after",
    )
    .sort((x, y) => (x.d_day ?? 99) - (y.d_day ?? 99));
  const toRecord = watch.filter((w) => w.step === "result");
  const changes = notis.slice(0, pc ? 6 : 3);
  const unread = notis.filter((n) => !n.read_at).length;

  const bell = token ? (
    <Link
      href="/notifications"
      aria-label={copy.noti.title}
      className="m-only"
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
    <Link href="/login" className="m-only" style={{ fontSize: 14, fontWeight: 600 }}>
      {t.login}
    </Link>
  );

  const loginBanner = !token && (
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
  );

  const todayBlock = token && (todo.length > 0 || toRecord.length > 0) && (
    <section className="section">
      <h2 style={{ marginBottom: 8 }}>
        {t.today} <span style={{ color: "var(--blue)" }}>{todo.length + toRecord.length}</span>
      </h2>
      {todo.map((w) => (
        <Link
          key={w.item_id}
          href={
            w.d_day != null && w.d_day <= 1
              ? `/item/${encodeURIComponent(w.item_id)}/bid-day`
              : `/watch/${encodeURIComponent(w.item_id)}`
          }
          className="menu-row"
        >
          <span style={{ minWidth: 0 }}>
            <b style={{ color: "var(--red)" }}>{dday(w.d_day)}</b> · {w.place}{" "}
            {w.building ?? w.usage}
            <span className="sub" style={{ display: "block" }}>
              {t.todoLine(copy.watch.steps[w.step] ?? "", w.d_day ?? 9)}
            </span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))}
      {toRecord.map((w) => (
        <Link key={w.item_id} href="/me" className="menu-row">
          <span style={{ minWidth: 0 }}>
            {w.place} {w.building ?? w.usage}
            <span className="sub" style={{ display: "block" }}>
              {t.record}
            </span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))}
    </section>
  );

  const changesBlock = token && changes.length > 0 && (
    <section className="section">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2>
          {t.changes} <span style={{ color: "var(--blue)" }}>{unread || ""}</span>
        </h2>
        <Link href="/notifications" className="sub">
          {t.allNoti} ›
        </Link>
      </div>
      {changes.map((n) => (
        <Link key={n.noti_id} href={n.link ?? "/notifications"} className="menu-row">
          <span style={{ minWidth: 0 }}>
            <span style={{ fontWeight: n.read_at ? 400 : 600 }}>{n.title}</span>
            {n.body && (
              <span className="sub" style={{ display: "block" }}>
                {n.body}
              </span>
            )}
          </span>
          <span className="sub" style={{ whiteSpace: "nowrap" }}>
            {n.created_at.slice(5, 10).replace("-", "/")}
          </span>
        </Link>
      ))}
    </section>
  );

  const closingBlock = closing.length > 0 && (
    <section className="section">
      <h2 style={{ marginBottom: 12 }}>{t.closing}</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
        {closing.map((c) => (
          <Link
            key={c.item_id}
            href={`/item/${encodeURIComponent(c.item_id)}`}
            style={{
              border: "1px solid var(--line)",
              borderRadius: 14,
              padding: 12,
              color: "inherit",
            }}
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
          </Link>
        ))}
      </div>
    </section>
  );

  const forMeBlock = (
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
      {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
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
      <div className={pc ? "card-grid" : ""}>
        {shown?.items.slice(0, pc ? 8 : 5).map((c) => (
          <ItemCard key={c.item_id} c={c} />
        ))}
      </div>
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
  );

  const whyBlock = !token && (
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
  );

  if (pc) {
    // 이번 주·다음 주 입찰 일정: 관심 물건 + 마감 임박
    const days = new Map<string, { id: string; label: string; mine: boolean }[]>();
    const seen = new Set<string>();
    for (const [c, mineFlag] of [
      ...watch.map((w) => [w, true] as const),
      ...(shown?.items ?? []).map((c) => [c, false] as const),
    ]) {
      if (!c.sale_date || c.d_day == null || c.d_day < 0 || c.d_day > 13 || seen.has(c.item_id))
        continue;
      seen.add(c.item_id);
      const l = days.get(c.sale_date) ?? [];
      l.push({ id: c.item_id, label: `${c.place} ${c.building ?? c.usage ?? ""}`, mine: mineFlag });
      days.set(c.sale_date, l);
    }
    const cal = [...days.entries()].sort(([a], [b]) => a.localeCompare(b));
    return (
      <main className="page">
        <PageHeader title={t.pcTitle} sub={summary} />
        {loginBanner}
        <div className="pc-grid g-64-36">
          <div>
            {todayBlock}
            {changesBlock}
            {forMeBlock}
          </div>
          <div>
            <section className="section">
              <h2 style={{ marginBottom: 8 }}>{t.calendar}</h2>
              {cal.length === 0 && <p className="sub">{t.calendarEmpty}</p>}
              {cal.map(([day, list]) => (
                <div key={day} style={{ padding: "8px 0", borderTop: "1px solid var(--line)" }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>
                    {day.slice(5).replace("-", "/")}
                  </div>
                  {list.map((x) => (
                    <Link
                      key={x.id}
                      href={`/item/${encodeURIComponent(x.id)}`}
                      style={{ display: "block", fontSize: 14, color: "inherit", padding: "2px 0" }}
                    >
                      {x.mine && (
                        <span className="chip green" style={{ marginRight: 6 }}>
                          {t.mine}
                        </span>
                      )}
                      {x.label}
                    </Link>
                  ))}
                </div>
              ))}
            </section>
            {token && (
              <section className="section">
                <h2>{copy.noti.title}</h2>
                <div className="sub">{t.notiSummary(notis.length, unread)}</div>
                <Link href="/notifications" className="menu-row">
                  <span>{t.allNoti}</span>
                  <span className="sub">›</span>
                </Link>
              </section>
            )}
            <section className="section">
              <h2>{t.myCond}</h2>
              <div className="sub">{summary}</div>
              <Link href="/start" className="menu-row">
                <span>{t.changeAnswers}</span>
                <span className="sub"></span>
              </Link>
            </section>
            {market && market.by_court.length > 0 && (
              <section className="section">
                <h2>{t.courtRate}</h2>
                <div className="sub">{t.courtRateSub}</div>
                {market.by_court.slice(0, 6).map((r) => (
                  <div key={r.court_code} className="line-row" style={{ fontSize: 14 }}>
                    <span>{r.court}</span>
                    <span>
                      <b>{Math.round(r.p50)}%</b> <span className="sub">{r.n}건</span>
                    </span>
                  </div>
                ))}
                <Link href="/pro/market" className="menu-row">
                  <span>{t.marketMore}</span>
                  <span className="sub">›</span>
                </Link>
              </section>
            )}
            {closingBlock}
            {whyBlock}
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <PageHeader title={copy.appName} right={bell} />
      {loginBanner}
      {changesBlock}
      {todayBlock}
      {closingBlock}
      {forMeBlock}
      {whyBlock}
      {!token && (
        <Link href="/login" className="btn kakao">
          {t.kakao}
        </Link>
      )}
    </main>
  );
}
