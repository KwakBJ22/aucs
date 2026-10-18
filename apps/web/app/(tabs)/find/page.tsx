"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { fetchItems, type FindStatus, type ItemList, type ResultCard } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";

const t = copy.find;
const KEY_STATUS = "aucs_find_status";
const KEY_RECENT = "aucs_recent_q";

function load(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function save(key: string, v: string): void {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* 저장 못 해도 계속 */
  }
}

// 끝난 사건 한 줄 (매각·취하·변경)
function ResultRow({ r }: { r: ResultCard }) {
  const body = (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--line)" }}>
      <div className="sub" style={{ margin: 0 }}>
        <b style={{ color: r.result === "매각" ? "var(--blue)" : "var(--muted)" }}>{r.result}</b> ·{" "}
        {r.sale_date} · {r.court} {r.case_no}
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, marginTop: 2 }}>
        {r.place} {r.building ?? r.usage}
      </div>
      {r.winning_bid_krw ? (
        <div style={{ fontSize: 14, marginTop: 2 }}>
          {t.sold(won(r.winning_bid_krw), r.sale_rate)}
        </div>
      ) : null}
    </div>
  );
  return r.item_id ? (
    <Link href={`/item/${r.item_id}`} style={{ color: "inherit", textDecoration: "none" }}>
      {body}
    </Link>
  ) : (
    body
  );
}

export default function Find() {
  const router = useRouter();
  const [sort, setSort] = useState<"deadline" | "rate">("deadline");
  const [status, setStatus] = useState<FindStatus>("active");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState(""); // 실제로 찾는 말 (입력 멈춘 뒤)
  const [focus, setFocus] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [list, setList] = useState<ItemList | null>(null);
  const [regions, setRegions] = useState<string[]>([]);

  useEffect(() => {
    const s = load(KEY_STATUS);
    if (s === "active" || s === "sold" || s === "withdrawn" || s === "all") setStatus(s);
    try {
      setRecent(JSON.parse(load(KEY_RECENT) ?? "[]") as string[]);
    } catch {
      setRecent([]);
    }
  }, []);

  useEffect(() => {
    const h = setTimeout(() => setQuery(q.trim()), 350);
    return () => clearTimeout(h);
  }, [q]);

  useEffect(() => {
    const p = loadProfile();
    setRegions(p?.regions ?? []);
    fetchItems({
      sigungu: p?.regions,
      maxCash: p?.cash,
      sort,
      limit: 100,
      q: query || undefined,
      status,
    })
      .then((r) => {
        if (r.exact_item_id) {
          remember(query);
          router.push(`/item/${r.exact_item_id}`);
          return;
        }
        setList(r);
      })
      .catch(() => setList({ total: 0, items: [], results: [] }));
  }, [sort, status, query]); // eslint-disable-line react-hooks/exhaustive-deps

  const remember = (word: string) => {
    if (!word) return;
    const next = [word, ...recent.filter((x) => x !== word)].slice(0, 5);
    setRecent(next);
    save(KEY_RECENT, JSON.stringify(next));
  };
  const pickStatus = (s: FindStatus) => {
    setStatus(s);
    save(KEY_STATUS, s);
  };
  const empty = list && list.items.length === 0 && !(list.results ?? []).length;

  return (
    <main className="page">
      <div className="topbar">
        <div className="brand">{t.title}</div>
      </div>
      <div style={{ display: "flex", gap: 8, position: "relative" }}>
        <input
          type="search"
          value={q}
          placeholder={t.searchPlaceholder}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setFocus(true)}
          onBlur={() => setTimeout(() => setFocus(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setQuery(q.trim());
              remember(q.trim());
            }
          }}
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 16,
            padding: "10px 12px",
            border: "1px solid var(--line)",
            borderRadius: 10,
            background: "transparent",
            color: "inherit",
          }}
        />
        <select
          value={status}
          onChange={(e) => pickStatus(e.target.value as FindStatus)}
          aria-label="상태"
          style={{
            fontSize: 15,
            padding: "0 8px",
            border: "1px solid var(--line)",
            borderRadius: 10,
            background: "transparent",
            color: "inherit",
          }}
        >
          {Object.entries(t.status).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        {focus && !q && recent.length > 0 && (
          <div
            style={{
              position: "absolute",
              top: "100%",
              left: 0,
              right: 0,
              zIndex: 5,
              background: "var(--bg)",
              border: "1px solid var(--line)",
              borderRadius: 10,
              padding: "6px 0",
              marginTop: 4,
            }}
          >
            <div className="sub" style={{ margin: "0 12px 4px", fontSize: 12 }}>
              {t.recent}
            </div>
            {recent.map((w) => (
              <button
                key={w}
                onMouseDown={() => {
                  setQ(w);
                  setQuery(w);
                }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  border: 0,
                  background: "none",
                  color: "inherit",
                  padding: "8px 12px",
                  fontSize: 15,
                }}
              >
                {w}
              </button>
            ))}
          </div>
        )}
      </div>
      {!query && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {regions.map((r) => (
            <span key={r} className="chip gray" style={{ fontSize: 13, padding: "6px 10px" }}>
              {r}
            </span>
          ))}
          {status !== "sold" &&
            status !== "withdrawn" &&
            (["deadline", "rate"] as const).map((s) => (
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
      )}
      <p className="sub">
        {query
          ? t.searching
          : list && status !== "sold" && status !== "withdrawn"
            ? `${t.total(list.total)} · ${t.mapSoon}`
            : ""}
      </p>
      <section className="section" style={{ paddingTop: 6, paddingBottom: 6 }}>
        {empty && <p className="sub">{t.noResult}</p>}
        {list?.items.map((c) => (
          <ItemCard key={c.item_id} c={c} />
        ))}
        {(list?.results ?? []).map((r) => (
          <ResultRow key={r.result_id} r={r} />
        ))}
      </section>
    </main>
  );
}
