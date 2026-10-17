"use client";

import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { fetchItems, type ItemList } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { loadProfile } from "@/lib/profile";

const t = copy.find;

export default function Find() {
  const [sort, setSort] = useState<"deadline" | "rate">("deadline");
  const [list, setList] = useState<ItemList | null>(null);
  const [regions, setRegions] = useState<string[]>([]);

  useEffect(() => {
    const p = loadProfile();
    setRegions(p?.regions ?? []);
    fetchItems({ sigungu: p?.regions, maxCash: p?.cash, sort, limit: 100 })
      .then(setList)
      .catch(() => setList({ total: 0, items: [] }));
  }, [sort]);

  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {regions.map((r) => (
          <span key={r} className="chip gray" style={{ fontSize: 13, padding: "6px 10px" }}>
            {r}
          </span>
        ))}
        {(["deadline", "rate"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSort(s)}
            className="chip"
            style={{
              fontSize: 13,
              padding: "6px 10px",
              border: 0,
              minHeight: 32,
              background: sort === s ? "var(--blue)" : "var(--gray-chip)",
              color: sort === s ? "#fff" : "var(--gray-text)",
            }}
          >
            {s === "deadline" ? t.sortDeadline : t.sortRate}
          </button>
        ))}
      </div>
      <p className="sub">
        {list ? t.total(list.total) : ""} · {t.mapSoon}
      </p>
      <section className="section" style={{ paddingTop: 6, paddingBottom: 6 }}>
        {list?.items.map((c) => (
          <ItemCard key={c.item_id} c={c} />
        ))}
      </section>
    </main>
  );
}
