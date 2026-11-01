"use client";

import { LoadError } from "@/components/load-error";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ItemCard } from "@/components/item-card";
import { fetchItems, type ItemList } from "@/lib/api/items";
import { condSummary } from "@/lib/cond";
import { copy } from "@/lib/copy.ko";
import { isStale } from "@/lib/noti";
import { dday, won } from "@/lib/format";
import { loadProfile, type Profile } from "@/lib/profile";
import { meApi, type Noti, type WatchCard } from "@/lib/api/me";
import { fetchMarket, type Market } from "@/lib/api/pro";
import { PageHeader } from "@/components/layout/page-header";
import { useIsPc } from "@/lib/use-pc";
import { useSession } from "@/lib/auth";
import { subscribePush } from "@/lib/push";
import { track } from "@/lib/track";

const t = copy.home;

export default function Home() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [mine, setMine] = useState<ItemList | null>(null);
  const [onbidSoon, setOnbidSoon] = useState<ItemList | null>(null); // 이번 주 마감 공매(10/28)
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
    await meApi.addSearch(token, condSummary({ sigungu: p.regions, max_cash: p.cash }), {
      sigungu: p.regions,
      max_cash: p.cash,
    });
    track("alert_on");
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
    fetchItems({
      sigungu: p.regions,
      maxCash: p.cash,
      limit: 5,
      source: "onbid",
      filter: { days_max: 3 },
    })
      .then(setOnbidSoon)
      .catch(() => setOnbidSoon(null)); // 공매가 안 와도 홈은 그대로
  }, [router, tries]);

  if (!profile) return null;
  const shown = mine && { ...mine, items: mine.items.filter((c) => !dropped.has(c.item_id)) };
  const closing = (shown?.items ?? [])
    .filter((c) => c.source !== "onbid" && c.d_day != null && c.d_day <= 7)
    .slice(0, 2);
  const onbidClosing = (onbidSoon?.items ?? []).filter((c) => !dropped.has(c.item_id)).slice(0, 4);
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
  const fresh = notis.filter((n) => !isStale(n)); // 지난 입찰일 알림은 홈에서 뺌(11/1)
  const changes = fresh.slice(0, pc ? 6 : 3);
  const unread = fresh.filter((n) => !n.read_at).length;

  const bell = token ? (
    <Link
      href="/notifications"
      aria-label={copy.noti.title}
      className="m-only mh-44 d-flex ai-center jc-end"
      style={{ minWidth: 44 }}
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
    <Link href="/login" className="m-only fs-md fw-6">
      {t.login}
    </Link>
  );

  const loginBanner = !token && (
    <Link
      href="/login"
      className="d-flex jc-between bg-blue-soft r-14 py-12 px-14 c-blue-text fs-md fw-6"
    >
      <span>{t.loginBanner}</span>
      <span aria-hidden="true">›</span>
    </Link>
  );

  const todayBlock = token && (todo.length > 0 || toRecord.length > 0) && (
    <section className="section">
      <h2 className="mb-8">
        {t.today} <span className="c-blue">{todo.length + toRecord.length}</span>
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
          <span className="minw-0">
            <b className="c-red">{dday(w.d_day)}</b> · {w.place} {w.building ?? w.usage}
            <span className="sub d-block">
              {t.todoLine(copy.watch.steps[w.step] ?? "", w.d_day ?? 9)}
            </span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))}
      {toRecord.map((w) => (
        <Link key={w.item_id} href="/me" className="menu-row">
          <span className="minw-0">
            {w.place} {w.building ?? w.usage}
            <span className="sub d-block">{t.record}</span>
          </span>
          <span className="sub">›</span>
        </Link>
      ))}
    </section>
  );

  const changesBlock = token && changes.length > 0 && (
    <section className="section">
      <div className="d-flex jc-between ai-baseline">
        <h2>
          {t.changes} <span className="c-blue">{unread || ""}</span>
        </h2>
        <Link href="/notifications" className="sub">
          {t.allNoti} ›
        </Link>
      </div>
      {changes.map((n) => (
        <Link key={n.noti_id} href={n.link ?? "/notifications"} className="menu-row">
          <span className="minw-0">
            <span style={{ fontWeight: n.read_at ? 400 : 600 }}>{n.title}</span>
            {n.body && <span className="sub d-block">{n.body}</span>}
          </span>
          <span className="sub nowrap">{n.created_at.slice(5, 10).replace("-", "/")}</span>
        </Link>
      ))}
    </section>
  );

  const smallCard = (c: (typeof closing)[number]) => (
    <Link
      key={c.item_id}
      href={`/item/${encodeURIComponent(c.item_id)}`}
      className="b-0 bg-panel r-14 p-12 c-inherit"
    >
      <div className="fs-xs fw-7 c-red d-flex jc-between">
        <span>
          {dday(c.d_day)} · {c.sale_date?.slice(5).replace("-", "/")}
        </span>
        {c.source === "onbid" && (
          <span className="fs-xs fw-6 py-0 px-6 r-4 b-0 bg-gray-chip c-text">
            {c.kind === "trust" ? copy.card.trust : copy.card.onbid}
          </span>
        )}
      </div>
      <div className="fs-md fw-6 mt-6">{c.place}</div>
      <div className="sub fs-xs nowrap" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
        {c.building ?? c.usage}
      </div>
      <div className="fs-base fw-7 mt-8">{won(c.min_price_krw)}</div>
      {c.min_rate != null && (
        <div className="sub fs-xs">
          {copy.card.ofAppraisal} {c.min_rate}%
        </div>
      )}
    </Link>
  );
  const closingBlock = closing.length > 0 && (
    <section className="section">
      <h2 className="mb-12">{t.closing}</h2>
      <div className="d-grid gap-10" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        {closing.map(smallCard)}
      </div>
    </section>
  );
  const onbidBlock = onbidClosing.length > 0 && (
    <section className="section">
      <div className="d-flex jc-between ai-baseline">
        <h2 className="mb-12">{t.onbidClosing}</h2>
        <Link href="/find?source=onbid" className="sub fs-sm">
          {t.onbidAll}
        </Link>
      </div>
      <div className="d-grid gap-10" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        {onbidClosing.map(smallCard)}
      </div>
      <div className="sub fs-xs mt-10">{t.onbidClosingSub}</div>
    </section>
  );

  const forMeBlock = (
    <section className="section">
      <div className="d-flex jc-between ai-baseline">
        <h2>
          {t.forMe} <span className="c-blue">{mine?.total ?? ""}</span>
        </h2>
        <Link href="/start" className="sub">
          {t.changeAnswers}
        </Link>
      </div>
      <div className="sub mb-4">{summary}</div>
      {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      <button
        className="btn bg-blue-soft c-blue-text mt-8 mb-4 mx-0 fs-md"
        style={{ height: 44 }}
        onClick={() => void turnOnAlert(profile)}
      >
        {copy.alert.button}
      </button>
      {alertMsg && <p className="sub mt-0 mb-4 mx-0">{alertMsg}</p>}
      {shown && shown.items.length === 0 && <p className="sub">{t.empty}</p>}
      <div className={pc ? "card-grid" : ""}>
        {shown?.items.slice(0, pc ? 8 : 5).map((c) => (
          <ItemCard key={c.item_id} c={c} />
        ))}
      </div>
      {mine && mine.total > 5 && (
        <Link href="/find?source=all" className="d-block ta-center pt-12 pb-0 px-0 fs-md fw-6">
          {copy.find.total(mine.total)} 모두 보기 ›
        </Link>
      )}
    </section>
  );

  const whyBlock = !token && (
    <section className="section">
      <h2 className="mb-8">{t.whyTitle}</h2>
      <div className="d-flex f-col gap-10 fs-md" style={{ lineHeight: 1.45 }}>
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
              <h2 className="mb-8">{t.calendar}</h2>
              {cal.length === 0 && <p className="sub">{t.calendarEmpty}</p>}
              {cal.map(([day, list]) => (
                <div key={day} className="py-8 px-0">
                  <div className="fw-7 fs-md">{day.slice(5).replace("-", "/")}</div>
                  {list.map((x) => (
                    <Link
                      key={x.id}
                      href={`/item/${encodeURIComponent(x.id)}`}
                      className="d-block fs-md c-inherit py-2 px-0"
                    >
                      {x.mine && <span className="chip green mr-6">{t.mine}</span>}
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
                  <div key={r.court_code} className="line-row fs-md">
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
            {onbidBlock}
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
      {onbidBlock}
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
