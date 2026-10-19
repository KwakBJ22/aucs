"use client";

import { PageHeader } from "@/components/layout/page-header";
import { useEffect, useState } from "react";
import Link from "next/link";
import { NeedLogin } from "@/components/need-login";
import { meApi, type Noti } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

export default function Notifications() {
  const { session, ready } = useSession();
  const [list, setList] = useState<Noti[] | null>(null);
  useEffect(() => {
    if (session)
      meApi
        .notifications(session.access_token)
        .then(setList)
        .catch(() => setList([]));
  }, [session]);
  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.noti.title} />;
  return (
    <main className="page">
      <PageHeader title={copy.noti.title} back="/home" />
      <section className="section">
        {list && list.length === 0 && <p className="sub">{copy.noti.empty}</p>}
        {list?.map((n) => (
          <Link
            key={n.noti_id}
            href={n.link ?? "/home"}
            className="menu-row"
            style={{ display: "block" }}
          >
            <div style={{ fontWeight: n.read_at ? 400 : 600 }}>{n.title}</div>
            {n.body && <div className="sub">{n.body}</div>}
          </Link>
        ))}
      </section>
    </main>
  );
}
