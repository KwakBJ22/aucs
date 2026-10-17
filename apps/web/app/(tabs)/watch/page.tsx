"use client";

import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { NeedLogin } from "@/components/need-login";
import { meApi, type WatchCard } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

export default function Watch() {
  const { session, ready } = useSession();
  const [list, setList] = useState<WatchCard[] | null>(null);

  useEffect(() => {
    if (session)
      meApi
        .watch(session.access_token)
        .then(setList)
        .catch(() => setList([]));
  }, [session]);

  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.tabs.watch} />;
  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{copy.watch.title}</div>
      </div>
      <section className="section" style={{ paddingTop: 6, paddingBottom: 6 }}>
        {list && list.length === 0 && <p className="sub">{copy.watch.empty}</p>}
        {list?.map((c) => (
          <ItemCard key={c.item_id} c={c} />
        ))}
      </section>
    </main>
  );
}
