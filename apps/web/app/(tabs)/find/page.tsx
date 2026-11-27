"use client";

import { useFresh } from "@/lib/api/fresh";
import { LoadError } from "@/components/load-error";
import { Delayed, SkCards, SkTable } from "@/components/skeleton";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { PickPanel } from "@/components/pick-panel";
import { BottomSheet } from "@/components/bottom-sheet";
import { FcChip, FindChips, FindFilters } from "@/components/find-filters";
import { PageHeader } from "@/components/layout/page-header";
import { dropPart, parseTalk, type Talk } from "@/lib/talk";
import {
  fetchRegions,
  fetchItems,
  itemsQuery,
  type FindFilter,
  type FindStatus,
  type ItemList,
  type ResultCard,
  type Source,
} from "@/lib/api/items";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { condSummary as condName } from "@/lib/cond";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { loadProfile } from "@/lib/profile";
import { regionsShort } from "@/lib/regions";
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
    <Link prefetch={false} href={`/item/${r.item_id}`} className="d-flex ai-center go c-inherit">
      {body}
    </Link>
  ) : (
    body
  );
}

export default function Find() {
  const router = useRouter();
  const [sort, setSort] = useState<"deadline" | "rate">("deadline");
  const fresh = useFresh(); // 지난번 자료를 먼저 그리고, 새 자료가 오면 다시 그림
  const [status, setStatus] = useState<FindStatus>("active");
  const [source, setSource] = useState<Source>("all");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState(""); // 실제로 찾는 말 (입력 멈춘 뒤)
  const [focus, setFocus] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [list, setList] = useState<ItemList | null>(null);
  const [regions, setRegions] = useState<string[]>([]);
  const [mapHref, setMapHref] = useState("/pro/map");
  const [regionNames, setRegionNames] = useState<string[]>([]);
  const [talk, setTalk] = useState<Talk | null>(null); // 말로 찾기로 알아들은 조건(칩)
  const [filter, setFilter] = useState<FindFilter>({});
  const [sheet, setSheet] = useState<"source" | "sort" | "cond" | "status" | null>(null);
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
    if (s === "active" || s === "sold" || s === "all") setStatus(s);
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
    const opts = {
      sigungu: talk?.sigungu ?? p?.regions,
      maxCash: talk?.filter.price_max ? undefined : p?.cash,
      homes: p?.homes,
      sort,
      limit: 100,
      q: query || undefined,
      status,
      filter: talk ? { ...filter, ...talk.filter } : filter,
      source: talk?.source ?? source,
    };
    setMapHref(`/pro/map?${itemsQuery(opts).toString()}`); // 지도로 보기도 같은 조건(11/12)
    fetchItems(opts)
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
  }, [sort, status, source, query, filter, prefsReady, tries, talk, fresh]); // eslint-disable-line react-hooks/exhaustive-deps

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
      .addSearch(session.access_token, condName({ sigungu: regions, ...filter }), {
        sigungu: regions,
        ...filter,
      })
      .then(() => setSaveMsg(t.saved))
      .catch(() => setSaveMsg(""));
  };

  const remember = (word: string) => {
    if (!word) return;
    const next = [word, ...recent.filter((x) => x !== word)].slice(0, 5);
    setRecent(next);
    save(KEY_RECENT, JSON.stringify(next));
  };
  const forget = (word: string) => {
    const next = recent.filter((x) => x !== word);
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

  // 최근 검색 창 · 알아들은 조건 줄 — 휴대폰 찾기 칸과 PC 찾기 줄이 같이 씀
  const recentBox = focus && !q && recent.length > 0 && (
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
        <div key={w} className="d-flex ai-center">
          <button
            onMouseDown={(e) => {
              e.preventDefault(); // 칸에서 손을 떼기 전에 고른 말을 넣음(예전엔 150ms 기다렸음)
              setQ(w);
              setQuery(w);
              setFocus(false);
            }}
            className="recent-word d-block ta-left py-12 px-12 fs-base"
          >
            {w}
          </button>
          <button
            aria-label={t.recentRemove(w)}
            onMouseDown={(e) => {
              e.preventDefault(); // 칸을 닫지 않고 이 말만 지움
              forget(w);
            }}
            className="icon-btn recent-x"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
  const talkRow = talk && (
    <div className="d-flex gap-6 f-wrap ai-center mt-10" aria-label={t.talkLabel}>
      <span className="sub m-0 fs-xs">{t.talkLabel}</span>
      {talk.parts.map((p) => (
        <button key={p.key} className="pill on" onClick={() => setTalk(dropPart(talk, p.key))}>
          {p.label} ×
        </button>
      ))}
    </div>
  );
  const inputProps = {
    type: "search",
    value: q,
    placeholder: t.searchPlaceholder,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setQ(e.target.value),
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        setQuery(q.trim());
        remember(q.trim());
      }
    },
  };

  // 휴대폰(11/23 M-Find): 찾기 칸 + 칩 한 줄(경매·공매 · 지역 · 줄 세우기 · 조건 · 진행 상태), 누르면 아래 창
  const searchIcon = (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
  const closed = status === "sold" || status === "withdrawn";
  const condN = Object.values(filter).filter(
    (v) => v != null && (!Array.isArray(v) || v.length > 0),
  ).length;
  const regionsShown = talk?.sigungu ?? regions;
  const searchBox = (
    <>
      <div className="find-bar pos-relative">
        {searchIcon}
        <input {...inputProps} aria-label={t.searchPlaceholder} />
        {recentBox}
      </div>
      {talkRow}
      <div className="m-chips quiet-scroll">
        {!closed && (
          <FcChip
            on={source !== "all"}
            label={t.source[source] ?? ""}
            onClick={() => setSheet("source")}
          />
        )}
        {!query && (
          <FcChip
            on={regionsShown.length > 0}
            label={
              regionsShown.length > 1
                ? t.chip.more(regionsShown[0]!, regionsShown.length - 1)
                : (regionsShown[0] ?? t.chip.region)
            }
            onClick={() => router.push("/start")}
          />
        )}
        {!query && !closed && (
          <FcChip
            on={false}
            label={sort === "deadline" ? t.sortDeadline : t.sortRate}
            onClick={() => setSheet("sort")}
          />
        )}
        <FcChip
          on={condN > 0}
          label={condN > 0 ? `${t.cond} ${condN}` : t.cond}
          onClick={() => setSheet("cond")}
        />
        <FcChip on={false} label={t.status[status] ?? ""} onClick={() => setSheet("status")} />
      </div>
    </>
  );
  // 하나 고르는 아래 창(경매·공매 · 줄 세우기 · 진행 상태)
  const one = <K extends string>(
    title: string,
    opts: [K, string][],
    v: K,
    pick: (k: K) => void,
  ) => (
    <BottomSheet label={title} onClose={() => setSheet(null)}>
      <b className="fs-lg">{title}</b>
      <div className="pills mt-12">
        {opts.map(([k, name]) => (
          <button
            key={k}
            className={v === k ? "on" : ""}
            onClick={() => {
              pick(k);
              setSheet(null);
            }}
          >
            {name}
          </button>
        ))}
      </div>
    </BottomSheet>
  );
  const sheetBox =
    sheet === "source"
      ? one(
          t.sourceLabel,
          (["all", "court", "onbid"] as const).map(
            (k) => [k, t.source[k] ?? ""] as [Source, string],
          ),
          source,
          pickSource,
        )
      : sheet === "sort"
        ? one(
            t.sortLabel,
            [
              ["deadline", t.sortDeadline],
              ["rate", t.sortRate],
            ],
            sort,
            setSort,
          )
        : sheet === "status"
          ? one(
              t.chip.status,
              Object.entries(t.status) as [FindStatus, string][],
              status,
              pickStatus,
            )
          : sheet === "cond" && (
              <BottomSheet
                label={t.cond}
                onClose={() => setSheet(null)}
                foot={
                  <>
                    <button className="btn secondary" onClick={saveCond}>
                      {t.saveCond}
                    </button>
                    <button className="btn primary" onClick={() => setSheet(null)}>
                      {list ? t.seeN(list.total) : t.seeAll}
                    </button>
                  </>
                }
              >
                <div className="d-flex jc-between ai-center mb-12">
                  <b className="fs-lg">{t.cond}</b>
                  <button className="fc-text" onClick={() => changeFilter({})}>
                    {t.condReset}
                  </button>
                </div>
                <FindFilters f={filter} onChange={changeFilter} saveMsg={saveMsg} sheet />
              </BottomSheet>
            );
  const countLine = (
    <>
      <p className="find-count">
        {query
          ? t.searching
          : list && status !== "sold" && status !== "withdrawn"
            ? t.total(list.total)
            : ""}
      </p>
    </>
  );
  const results = (
    <>
      {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      {!failed && empty && <p className="sub">{t.noResult}</p>}
      {!failed && !list && (
        <Delayed>
          <SkCards n={6} />
        </Delayed>
      )}
      {list?.items.map((c) => (
        <ItemCard key={c.item_id} c={c} />
      ))}
      {(list?.results ?? []).map((r) => (
        <ResultRow key={r.result_id} r={r} />
      ))}
    </>
  );

  const mapLink = (
    <Link href={mapHref} className="btn soft sm nowrap">
      {copy.mapView.open} ›
    </Link>
  );

  // PC(11/22 디자인): 왼쪽 조건 칸을 없애고 넓은 찾기 줄 + 조건 칩 한 줄 → 목록 | 고른 물건
  if (pc)
    return (
      <main className="page wide">
        <PageHeader title={t.title} sub={regionsShort(regions)} right={mapLink} />
        <div className="find-bar pos-relative">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input {...inputProps} aria-label={t.searchPlaceholder} />
          {recentBox}
        </div>
        {talkRow}
        <FindChips
          f={filter}
          onChange={changeFilter}
          onSave={saveCond}
          saveMsg={saveMsg}
          regions={talk?.sigungu ?? regions}
          source={source}
          onSource={pickSource}
          status={status}
          onStatus={pickStatus}
        />
        <div className="find-grid">
          <div className="minw-0">
            <div className="find-head">
              {query ? (
                <span className="sub">{t.searching}</span>
              ) : (
                <b>
                  {list && status !== "sold" && status !== "withdrawn" ? t.total(list.total) : ""}
                </b>
              )}
              <span className="d-flex ai-center gap-10">
                {status !== "sold" && status !== "withdrawn" && (
                  <select
                    className="sort-sel"
                    aria-label={t.sortLabel}
                    value={sort}
                    onChange={(e) => setSort(e.target.value as "deadline" | "rate")}
                  >
                    <option value="deadline">{t.sortDeadline}</option>
                    <option value="rate">{t.sortRate}</option>
                  </select>
                )}
                <span className="scope-seg" role="group">
                  <button className={!asTable ? "on" : ""} onClick={() => setAsTable(false)}>
                    {t.viewCard}
                  </button>
                  <button className={asTable ? "on" : ""} onClick={() => setAsTable(true)}>
                    {t.viewTable}
                  </button>
                </span>
              </span>
            </div>
            <section className="section mt-0 find-list">
              {empty && <p className="sub">{t.noResult}</p>}
              {failed && <LoadError onRetry={() => setTries((n) => n + 1)} />}
              {!failed && !list && (
                <Delayed>{asTable ? <SkTable rows={10} cols={5} /> : <SkCards n={6} />}</Delayed>
              )}
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
          </div>
          <div
            className="pc-sticky oy-auto quiet-scroll"
            style={{ maxHeight: "calc(100dvh - 140px)" }}
          >
            <PickPanel id={pick} />
          </div>
        </div>
      </main>
    );

  return (
    <main className="page">
      <PageHeader
        title={t.title}
        right={
          <Link href={mapHref} className="link fs-sm px-6">
            {copy.mapView.open}
          </Link>
        }
      />
      {searchBox}
      {countLine}
      <section className="section find-list">{results}</section>
      {sheetBox}
    </main>
  );
}
