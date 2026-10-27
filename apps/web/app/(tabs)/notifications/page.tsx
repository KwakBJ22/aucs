"use client";

import { LoadError } from "@/components/load-error";
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
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);
  useEffect(() => {
    if (!session) return;
    setFailed(false);
    meApi
      .notifications(session.access_token)
      .then(setList)
      .catch(() => setFailed(true));
  }, [session, tries]);
  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.noti.title} />;
  const group = (n: Noti): "change" | "todo" | "new" => {
    const k = n.kind ?? "";
    if (!k || k === "new_match") return "new";
    if (k.startsWith("deadline_") || k === "bid_morning" || k === "spec_open") return "todo";
    return "change";
  };
  const groups = (["change", "todo", "new"] as const).map((g) => ({
    g,
    rows: (list ?? []).filter((n) => group(n) === g),
  }));
  return (
    <main className="page">
      <PageHeader title={copy.noti.title} back="/home" />
      {failed && !list && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      {list && list.length === 0 && (
        <section className="section">
          <p className="sub">{copy.noti.empty}</p>
        </section>
      )}
      <div className="pc-grid g-3">
        {groups
          .filter((x) => x.rows.length > 0)
          .map(({ g, rows }) => (
            <section key={g} className="section">
              <h2>
                {copy.noti.groups[g]} <span className="sub">{rows.length}</span>
              </h2>
              <div className="sub">{copy.noti.groupSub[g]}</div>
              {rows.map((n) => (
                <Link
                  key={n.noti_id}
                  href={n.link ?? "/home"}
                  className="menu-row"
                  style={{ display: "block" }}
                >
                  <div style={{ fontWeight: n.read_at ? 400 : 600 }}>{n.title}</div>
                  {n.body && <div className="sub">{n.body}</div>}
                  <div className="sub" style={{ fontSize: 12 }}>
                    {n.created_at.slice(5, 16).replace("T", " ").replace("-", "/")}
                  </div>
                </Link>
              ))}
            </section>
          ))}
      </div>
    </main>
  );
}
