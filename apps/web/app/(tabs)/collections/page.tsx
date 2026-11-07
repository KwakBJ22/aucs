"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { PageHeader } from "@/components/layout/page-header";
import { LoadError } from "@/components/load-error";
import { Delayed, SkRows } from "@/components/skeleton";
import { fetchCollections, type Collections } from "@/lib/api/items";
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
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);

  useEffect(() => {
    setProfile(loadProfile());
    setReady(true);
  }, []);
  const mine = !all && Boolean(profile?.regions?.length);
  const opts = mine ? { sigungu: profile?.regions ?? [], maxCash: profile?.cash ?? null } : {};

  // 칩 건수와 고른 모음 목록을 한 번에 받음(모음을 바꿔도 건수는 지난 것을 그대로 보임)
  useEffect(() => {
    if (!ready) return;
    setFailed(false);
    fetchCollections({ ...opts, key, limit: 60 })
      .then((d) => setData({ key, all: !mine, d }))
      .catch(() => setFailed(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, mine, key, tries]);
  const sum = data && data.all === !mine ? data.d : null;

  const go = (k: string, scope: boolean) =>
    router.replace(`/collections?key=${k}${scope ? "&scope=all" : ""}`, { scroll: false });
  const cur = t.list.find(([k]) => k === key);
  const rows = data && data.key === key && data.all === !mine ? (data.d[key]?.items ?? []) : null;

  return (
    <main className="page">
      <PageHeader title={t.title} />
      <div className="d-flex jc-between ai-center gap-8 f-wrap">
        <p className="sub m-0">{t.sub}</p>
        <div className="pills" role="group">
          <button className={!all ? "on" : ""} onClick={() => go(key, false)}>
            {t.mine}
          </button>
          <button className={all ? "on" : ""} onClick={() => go(key, true)}>
            {t.all}
          </button>
        </div>
      </div>
      {!all && ready && !profile?.regions?.length && (
        <Link href="/start" className="note blue d-block mt-12">
          {t.noProfile} ›
        </Link>
      )}

      <div className="col-chips quiet-scroll" role="tablist">
        {t.list
          .filter(([k]) => k === key || !sum || (sum[k]?.total ?? 0) > 0) // 빈 모음 칩은 숨김(11/7)
          .map(([k, name]) => (
            <button
              key={k}
              role="tab"
              aria-selected={k === key}
              className={`col-chip${k === key ? " on" : ""}`}
              onClick={() => go(k, all)}
            >
              <b>{name}</b>
              <span className="num">{sum ? t.count(sum[k]?.total ?? 0) : "·"}</span>
            </button>
          ))}
      </div>

      {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      <section className="section">
        <h2>{cur?.[1]}</h2>
        <p className="sub mt-0">{cur?.[2]}</p>
        {rows === null && !failed && (
          <Delayed>
            <SkRows n={6} />
          </Delayed>
        )}
        {rows?.length === 0 && <p className="sub">{t.empty}</p>}
        <div className="col-list">
          {rows?.map((c) => (
            <ItemCard key={c.item_id} c={c} why={c.why} />
          ))}
        </div>
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
