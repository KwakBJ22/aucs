"use client";

import { LoadError } from "@/components/load-error";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { PickPanel } from "@/components/pick-panel";
import { FindFilters, filterSummary } from "@/components/find-filters";
import { PageHeader } from "@/components/layout/page-header";
import { dropPart, parseTalk, type Talk } from "@/lib/talk";
import {
  fetchRegions,
  fetchItems,
  type FindFilter,
  type FindStatus,
  type ItemList,
  type ResultCard,
  type Source,
} from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";
import { useIsPc } from "@/lib/use-pc";

const t = copy.find;
const KEY_STATUS = "aucs_find_status";
const KEY_RECENT = "aucs_recent_q";
const KEY_FILTER = "aucs_find_filter";
const KEY_SOURCE = "aucs_find_source"; // 전체·경매·공매(10/28) — 기본은 함께 보기
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
    <div className="py-12 px-0">
      <div className="sub m-0">
        <b style={{ color: r.result === "매각" ? "var(--blue)" : "var(--muted)" }}>{r.result}</b> ·{" "}
        {r.sale_date} · {r.court} {r.case_no}
      </div>
      <div className="fs-base fw-6 mt-2">
        {r.place} {r.building ?? r.usage}
      </div>
      {r.winning_bid_krw ? (
        <div className="fs-md mt-2">{t.sold(won(r.winning_bid_krw), r.sale_rate)}</div>
      ) : null}
    </div>
  );
  return r.item_id ? (
    <Link href={`/item/${r.item_id}`} className="c-inherit td-none">
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
  const [source, setSource] = useState<Source>("all");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState(""); // 실제로 찾는 말 (입력 멈춘 뒤)
  const [focus, setFocus] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [list, setList] = useState<ItemList | null>(null);
  const [regions, setRegions] = useState<string[]>([]);
  const [regionNames, setRegionNames] = useState<string[]>([]);
  const [talk, setTalk] = useState<Talk | null>(null); // 말로 찾기로 알아들은 조건(칩)
  const [filter, setFilter] = useState<FindFilter>({});
  const [condOpen, setCondOpen] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [pick, setPick] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);
  const [prefsReady, setPrefsReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0); // 이 기기에 기억한 조건을 읽은 뒤에 한 번만 부름
  const pc = useIsPc();
  const { session } = useSession();

  useEffect(() => {
    const s = load(KEY_STATUS);
    if (s === "active" || s === "sold" || s === "withdrawn" || s === "all") setStatus(s);
    // 주소에 ?source= 가 있으면 그것(홈 「이번 주 마감 공매 · 전체」 → 공매만, 11/1), 없으면 기억한 것
    const fromUrl = new URLSearchParams(window.location.search).get("source");
    const src = fromUrl ?? load(KEY_SOURCE);
    if (src === "court" || src === "onbid") setSource(src);
    else if (fromUrl === "all") setSource("all");
    try {
      setFilter(JSON.parse(load(KEY_FILTER) ?? "{}") as FindFilter);
    } catch {
      setFilter({});
    }
    try {
      setRecent(JSON.parse(load(KEY_RECENT) ?? "[]") as string[]);
    } catch {
      setRecent([]);
    }
    setPrefsReady(true);
  }, []);

  useEffect(() => {
    fetchRegions()
      .then((r) => setRegionNames(r.map((x) => x.sigungu)))
      .catch(() => {});
  }, []);
  // 다른 화면에서 /find?q=… 로 오면 그 말로 바로 찾기(11/1, 「같은 단지 다른 물건 보기」)
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("q")?.trim();
    if (v) {
      setQ(v);
      setQuery(v);
    }
  }, []);
  useEffect(() => {
    const h = setTimeout(() => setQuery(q.trim()), 350);
    return () => clearTimeout(h);
  }, [q]);
  // 말로 찾기: 「수지 30평대 7억 이하」 → 조건 칩, 남은 말만 검색어로
  useEffect(() => {
    if (!query || !regionNames.length) return;
    const tk = parseTalk(query, regionNames);
    if (!tk) return;
    setTalk(tk);
    setQ(tk.rest);
    setQuery(tk.rest);
  }, [query, regionNames]);

  useEffect(() => {
    if (!prefsReady) return; // 예전엔 빈 조건으로 한 번, 기억한 조건으로 또 한 번 불렀음(10/27)
    let stale = false; // 빨리 고치면 늦게 온 앞 결과가 새 결과를 덮지 않게
    setFailed(false);
    const p = loadProfile();
    setRegions(p?.regions ?? []);
    fetchItems({
      sigungu: talk?.sigungu ?? p?.regions,
      maxCash: talk?.filter.price_max ? undefined : p?.cash,
      sort,
      limit: 100,
      q: query || undefined,
      status,
      filter: talk ? { ...filter, ...talk.filter } : filter,
      source: talk?.source ?? source,
    })
      .then((r) => {
        if (stale) return;
        if (r.exact_item_id) {
          remember(query);
          router.push(`/item/${r.exact_item_id}`);
          return;
        }
        setList(r);
        setPick((p) =>
          p && r.items.some((x) => x.item_id === p) ? p : (r.items[0]?.item_id ?? null),
        );
      })
      .catch(() => !stale && setFailed(true)); // 빈 목록처럼 보이지 않게 오류로
    return () => {
      stale = true;
    };
  }, [sort, status, source, query, filter, prefsReady, tries, talk]); // eslint-disable-line react-hooks/exhaustive-deps

  const changeFilter = (f: FindFilter) => {
    setFilter(f);
    setSaveMsg("");
    save(KEY_FILTER, JSON.stringify(f));
  };
  const saveCond = () => {
    if (!session) {
      router.push("/login");
      return;
    }
    meApi
      .addSearch(session.access_token, copy.alert.name, { sigungu: regions, ...filter })
      .then(() => setSaveMsg(t.saved))
      .catch(() => setSaveMsg(""));
  };

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
  const pickSource = (s: Source) => {
    setSource(s);
    save(KEY_SOURCE, s);
  };
  const empty = list && list.items.length === 0 && !(list.results ?? []).length;

  const searchBox = (
    <>
      <div className="d-flex gap-8 pos-relative">
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
          className="f-1 minw-0 fs-base py-10 px-12 b-0 r-14 bg-panel c-inherit"
        />
        <select
          value={status}
          onChange={(e) => pickStatus(e.target.value as FindStatus)}
          aria-label="상태"
          className="fs-base py-0 px-8 b-0 r-14 bg-panel c-inherit"
        >
          {Object.entries(t.status).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        {focus && !q && recent.length > 0 && (
          <div
            className="pos-absolute bg-surface b-0 r-14 py-6 px-0 mt-4"
            style={{
              top: "100%",
              left: 0,
              right: 0,
              zIndex: 5,
              boxShadow: "0 6px 24px rgba(0,0,0,0.12)",
            }}
          >
            <div className="sub mt-0 mb-4 mx-12 fs-xs">{t.recent}</div>
            {recent.map((w) => (
              <button
                key={w}
                onMouseDown={() => {
                  setQ(w);
                  setQuery(w);
                }}
                className="d-block w-full ta-left b-0 bg-none c-inherit py-8 px-12 fs-base"
              >
                {w}
              </button>
            ))}
          </div>
        )}
      </div>
      {talk && (
        <div className="d-flex gap-6 f-wrap ai-center mt-10" aria-label={t.talkLabel}>
          <span className="sub m-0 fs-xs">{t.talkLabel}</span>
          {talk.parts.map((p) => (
            <button
              key={p.key}
              className="chip b-0 mh-32 bg-blue-soft c-blue-text"
              onClick={() => setTalk(dropPart(talk, p.key))}
            >
              {p.label} ×
            </button>
          ))}
        </div>
      )}
      {status !== "sold" && status !== "withdrawn" && (
        <div className="pills mt-10" role="group" aria-label={t.sourceLabel}>
          {(["all", "court", "onbid"] as const).map((s) => (
            <button key={s} className={source === s ? "on" : ""} onClick={() => pickSource(s)}>
              {t.source[s]}
            </button>
          ))}
        </div>
      )}
      {!query && (
        <div className="d-flex gap-8 f-wrap mt-10">
          {(talk?.sigungu ? [] : regions).map((r) => (
            <span key={r} className="chip gray fs-sm py-6 px-10">
              {r}
            </span>
          ))}
          {status !== "sold" &&
            status !== "withdrawn" &&
            (["deadline", "rate"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSort(s)}
                className="chip fs-sm py-6 px-10 b-0 mh-32"
                style={{
                  background: sort === s ? "var(--blue)" : "var(--gray-chip)",
                  color: sort === s ? "#fff" : "var(--gray-text)",
                }}
              >
                {s === "deadline" ? t.sortDeadline : t.sortRate}
              </button>
            ))}
        </div>
      )}
    </>
  );
  const countLine = (
    <>
      <p className="sub">
        {query
          ? t.searching
          : list && status !== "sold" && status !== "withdrawn"
            ? pc
              ? t.total(list.total)
              : `${t.total(list.total)} · ${t.mapSoon}`
            : ""}
      </p>
    </>
  );
  const condSummary = filterSummary(filter);
  const filters = (
    <FindFilters f={filter} onChange={changeFilter} onSave={saveCond} saveMsg={saveMsg} />
  );
  const results = (
    <>
      {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      {!failed && empty && <p className="sub">{t.noResult}</p>}
      {list?.items.map((c) => (
        <ItemCard key={c.item_id} c={c} />
      ))}
      {(list?.results ?? []).map((r) => (
        <ResultRow key={r.result_id} r={r} />
      ))}
    </>
  );

  if (pc)
    return (
      <main className="page">
        <PageHeader title={t.title} sub={regions.join(" · ")} />
        <div className="pc-grid g-18-34-48">
          <section
            className="section pc-sticky mt-0 oy-auto quiet-scroll"
            style={{ maxHeight: "calc(100vh - 140px)" }}
          >
            <h2>{t.cond}</h2>
            {filters}
          </section>
          <section className="section mt-0">
            {searchBox}
            <div className="d-flex jc-between ai-center">
              {countLine}
              <div className="pills">
                <button className={!asTable ? "on" : ""} onClick={() => setAsTable(false)}>
                  {t.viewCard}
                </button>
                <button className={asTable ? "on" : ""} onClick={() => setAsTable(true)}>
                  {t.viewTable}
                </button>
              </div>
            </div>
            {empty && <p className="sub">{t.noResult}</p>}
            {asTable ? (
              <div className="ox-auto">
                <table className="pro-table">
                  <thead>
                    <tr>
                      <th>{t.cols.date}</th>
                      <th>{t.cols.place}</th>
                      <th>{t.cols.min}</th>
                      <th>{t.cols.rate}</th>
                      <th>{t.cols.failed}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list?.items.map((c) => (
                      <tr
                        key={c.item_id}
                        onClick={() => setPick(c.item_id)}
                        className={`${pick === c.item_id ? "row-on" : ""} cur-pointer`}
                      >
                        <td>{dday(c.d_day)}</td>
                        <td>
                          {c.place} {c.building ?? c.usage}
                        </td>
                        <td>{won(c.min_price_krw)}</td>
                        <td>{c.min_rate}</td>
                        <td>{c.failed_count ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              list?.items.map((c) => (
                <div
                  key={c.item_id}
                  className={pick === c.item_id ? "pick-on" : ""}
                  onClickCapture={(e) => {
                    if (pick !== c.item_id) {
                      e.preventDefault();
                      setPick(c.item_id);
                    }
                  }}
                >
                  <ItemCard c={c} />
                </div>
              ))
            )}
            {(list?.results ?? []).map((r) => (
              <ResultRow key={r.result_id} r={r} />
            ))}
          </section>
          <div
            className="pc-sticky oy-auto quiet-scroll"
            style={{ maxHeight: "calc(100vh - 140px)" }}
          >
            <section className="section map-box mt-0">
              <span className="sub">{t.mapSoon}</span>
            </section>
            <PickPanel id={pick} />
          </div>
        </div>
      </main>
    );

  return (
    <main className="page">
      <PageHeader title={t.title} />
      {searchBox}
      <button className="cond-row" onClick={() => setCondOpen(!condOpen)}>
        <span>
          <b>{t.cond}</b> <span className="sub">{condSummary || t.condOpen}</span>
        </span>
        <span className="sub">{condOpen ? "▴" : "›"}</span>
      </button>
      {condOpen && <section className="section">{filters}</section>}
      {countLine}
      <section className="section pt-6 pb-6">{results}</section>
    </main>
  );
}
