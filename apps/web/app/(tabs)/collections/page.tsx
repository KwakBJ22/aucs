"use client";

import { useFresh } from "@/lib/api/fresh";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CollectionIcon } from "@/components/collection-icon";
import { ItemCard } from "@/components/item-card";
import { UpcomingCard } from "@/components/upcoming-card";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { Delayed, SkRows } from "@/components/skeleton";
import { fetchCollections, fetchUpcoming, type Collections, type Upcoming } from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy, type CollectionKey } from "@/lib/copy.ko";
import { loadProfile, type Profile } from "@/lib/profile";

const t = copy.collections;
const KEYS = t.list.map(([k]) => k);

// 모아 보기(11/7): 위에 모음 칩(건수) → 고른 모음의 물건(이유 한 줄). 주소에 모음·범위를 남겨 돌아와도 제자리(3-9).
function CollectionsView() {
  const router = useRouter();
  const sp = useSearchParams();
  const key = (KEYS as string[]).includes(sp.get("key") ?? "")
    ? (sp.get("key") as CollectionKey)
    : "cheap";
  const all = sp.get("scope") === "all";
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ready, setReady] = useState(false);
  const [data, setData] = useState<{ key: string; all: boolean; d: Collections } | null>(null);
  const fresh = useFresh(); // 지난번 자료를 먼저 그리고, 새 자료가 오면 다시 그림
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);
  // 곧 나올 물건(11/27): 물건이 아니라 공고 전 사건 — 따로 받음(건수는 칩에, 목록은 그 모음을 고를 때)
  const up = key === "upcoming";
  const [upData, setUpData] = useState<{
    all: boolean;
    total: number;
    page: number;
    rows: Upcoming[];
  } | null>(null);
  const [upIds, setUpIds] = useState<Set<string>>(new Set());
  const { session } = useSession();
  const token = session?.access_token ?? null;

  useEffect(() => {
    setProfile(loadProfile());
    setReady(true);
  }, []);
  const mine = !all && Boolean(profile?.regions?.length);
  const opts = mine
    ? { sigungu: profile?.regions ?? [], maxCash: profile?.cash ?? null, homes: profile?.homes }
    : {};

  // 칩 건수와 고른 모음 목록을 한 번에 받음(모음을 바꿔도 건수는 지난 것을 그대로 보임)
  useEffect(() => {
    if (!ready) return;
    setFailed(false);
    // 곧 나올 물건을 볼 때는 물건 모음은 건수만(1건)
    fetchCollections({ ...opts, key: up ? "cheap" : key, limit: up ? 1 : 60 })
      .then((d) => setData({ key, all: !mine, d }))
      .catch(() => setFailed(true));
    fetchUpcoming({ sigungu: mine ? (profile?.regions ?? []) : [] })
      .then((u) => setUpData({ all: !mine, total: u.total, page: 1, rows: u.items }))
      .catch(() => setFailed(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, mine, key, tries, fresh]);

  useEffect(() => {
    if (!up || !token) return;
    meApi
      .upcomingIds(token)
      .then((xs) => setUpIds(new Set(xs)))
      .catch(() => {});
  }, [up, token]);

  const upMore = () => {
    if (!upData) return;
    const page = upData.page + 1;
    fetchUpcoming({ sigungu: mine ? (profile?.regions ?? []) : [], page })
      .then((u) => setUpData({ ...upData, page, rows: [...upData.rows, ...u.items] }))
      .catch(() => setFailed(true));
  };
  const upToggle = (k: string) => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    const on = !upIds.has(k);
    setUpIds((s) => {
      const n = new Set(s);
      if (on) n.add(k);
      else n.delete(k);
      return n;
    });
    void meApi.setUpcoming(token, k, on);
  };
  const sum = data && data.all === !mine ? data.d : null;
  const upNow = upData && upData.all === !mine ? upData : null;
  const total = (k: string) => (k === "upcoming" ? (upNow?.total ?? 0) : (sum?.[k]?.total ?? 0));

  const go = (k: string, scope: boolean) =>
    router.replace(`/collections?key=${k}${scope ? "&scope=all" : ""}`, { scroll: false });
  const cur = t.list.find(([k]) => k === key);
  const rows = up
    ? null
    : data && data.key === key && data.all === !mine
      ? (data.d[key]?.items ?? [])
      : null;

  return (
    <main className="page">
      <PageHeader title={t.title} />
      <div className="d-flex jc-between ai-center gap-8 f-wrap">
        <p className="sub m-0">{t.sub}</p>
        <div className="scope-seg" role="group">
          <button className={!all ? "on" : ""} onClick={() => go(key, false)}>
            {t.mine}
          </button>
          <button className={all ? "on" : ""} onClick={() => go(key, true)}>
            {t.all}
          </button>
        </div>
      </div>
      {!all && ready && !profile?.regions?.length && (
        <Link href="/start" className="note blue d-flex go mt-12">
          {t.noProfile}
        </Link>
      )}

      <div className="col-chips quiet-scroll" role="tablist">
        {t.list
          .filter(([k]) => k === key || !sum || total(k) > 0) // 빈 모음 칩은 숨김(11/7)
          .map(([k, name]) => (
            <button
              key={k}
              role="tab"
              aria-selected={k === key}
              className={`col-chip${k === key ? " on" : ""}`}
              onClick={() => go(k, all)}
            >
              <CollectionIcon k={k} />
              <b>{name}</b>
              <span className="num">{sum ? t.count(total(k)) : "·"}</span>
            </button>
          ))}
      </div>

      {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      <section className="section">
        <h2>{cur?.[1]}</h2>
        <p className="sub mt-0">{cur?.[2]}</p>
        {(up ? upNow === null : rows === null) && !failed && (
          <Delayed>
            <SkRows n={6} />
          </Delayed>
        )}
        {(up ? upNow?.rows.length === 0 : rows?.length === 0) && <p className="sub">{t.empty}</p>}
        <div className="col-list">
          {rows?.map((c) => (
            <ItemCard key={c.item_id} c={c} why={c.why} />
          ))}
          {up &&
            upNow?.rows.map((u) => {
              const k = `${u.court_code}:${u.case_no}`;
              return <UpcomingCard key={k} u={u} on={upIds.has(k)} onToggle={() => upToggle(k)} />;
            })}
        </div>
        {up && upNow && upNow.rows.length < upNow.total && (
          <button className="btn soft w-full mt-12" onClick={upMore}>
            {copy.upcoming.more}
          </button>
        )}
      </section>
    </main>
  );
}

export default function CollectionsPage() {
  return (
    <Suspense>
      <CollectionsView />
    </Suspense>
  );
}
