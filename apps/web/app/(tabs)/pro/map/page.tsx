"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { PageHeader } from "@/components/layout/page-header";
import {
  fetchMapItems,
  type ItemCard as Card,
  type MapItems,
  type MapSold,
  type MapStation,
} from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won, wonShort } from "@/lib/format";
import { loadNaverMaps, type NMap, type NMarker, type NaverMaps } from "@/lib/naver-map";

const t = copy.mapView;
const SEOUL: [number, number] = [37.5665, 126.978];
const WALKS = [5, 10, 15] as const;
const NAME_ZOOM = 14; // 이보다 멀리서 보면 역 이름이 서로 겹쳐 어느 역인지 못 가림 — 역 표시를 안 냄(11/14 대표님)
type Color = "one" | "risk" | "market";
const COLORS: Color[] = ["risk", "market"]; // 안 고르면 한 색("one")
// 지도에서 더 좁히기(11/14) — 받은 물건을 화면에서 거름
const NARROW = ["failed", "cheap", "safe"] as const;
type Narrow = (typeof NARROW)[number];
const big = (c: Card) => c.top_signal?.level === "fatal" || c.top_signal?.level === "high";
const KEEP: Record<Narrow, (c: Card) => boolean> = {
  failed: (c) => !!c.failed_count,
  cheap: (c) => (c.vs_market_pct ?? 0) > 0,
  safe: (c) => !big(c),
};
// 색 뜻(작은 색 점 + 한마디) — 점 색과 같은 이름
const LEGEND: Record<Color, string[]> = {
  one: [],
  risk: ["red", "orange", "blue"],
  market: ["red", "orange", "blue", "gray"],
};

// 신호색상(11/14 대표님): 안 고르면 한 색(파랑). 고르면 한 가지 뜻으로만 나누고, 두 가지 모두 빨강 = 조심 · 주황 = 보통 · 파랑 = 좋음.
// 「위험」: 큰 위험 빨강 · 유찰 주황 · 그 밖 파랑 / 「시세 대비」: 시세보다 비쌈 빨강 · 조금 쌈 주황 · 20% 넘게 쌈 파랑 · 시세 없음 회색
function tone(c: Card, color: Color): string {
  if (color === "one") return "blue";
  if (color === "market") {
    const p = c.vs_market_pct;
    if (p == null) return "gray";
    if (p <= 0) return "red";
    return p >= 20 ? "blue" : "orange";
  }
  if (big(c)) return "red";
  if (c.failed_count) return "orange";
  return "blue";
}

function pinText(c: Card, color: Color): string {
  const p = c.vs_market_pct;
  if (color === "market" && p != null) return `${p > 0 ? "-" : "+"}${Math.abs(p)}%`;
  return wonShort(c.min_price_krw);
}

// 두 점 사이 직선거리(m) — 한 화면 안이라 평면 어림(API 와 같은 셈)
function nearM(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const dy = (aLat - bLat) * 111_320;
  const dx = (aLon - bLon) * 111_320 * Math.cos((aLat * Math.PI) / 180);
  return Math.hypot(dx, dy);
}

// 화면 크기에 맞춰 가까운 점끼리 묶음(확대할수록 풀림) — 칸 크기는 확대 단계로
function cluster(items: Card[], zoom: number): { lat: number; lon: number; list: Card[] }[] {
  const cell = 0.5 / 2 ** (zoom - 9);
  const box = new Map<string, Card[]>();
  for (const c of items) {
    if (c.lat == null || c.lon == null) continue;
    const k = `${Math.floor(c.lat / cell)}:${Math.floor(c.lon / cell)}`;
    box.set(k, [...(box.get(k) ?? []), c]);
  }
  return [...box.values()].map((list) => ({
    lat: list.reduce((s, c) => s + (c.lat ?? 0), 0) / list.length,
    lon: list.reduce((s, c) => s + (c.lon ?? 0), 0) / list.length,
    list,
  }));
}

// 고른 것(역세권 · 점 색 · 낙찰 사례)은 주소에 둠 — 새로고침 · 뒤로 가기 · 링크 보내기에 그대로(11/13)
function setParam(k: string, v: string | null) {
  const q = new URLSearchParams(window.location.search);
  if (v) q.set(k, v);
  else q.delete(k);
  const s = q.toString();
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname + (s ? `?${s}` : ""),
  );
}

// 지도 분석(11/12 대표님): 찾기 조건 그대로 · 보이는 범위의 물건만 받아 점으로, 오른쪽(휴대폰은 아래) 목록
// 11/13: 역세권 보기(역까지 걸어서 5 · 10 · 15분 안 + 역마다 물건 수) · 시세 대비 점 색 · 낙찰 사례 겹쳐 보기
export default function MapPage() {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<NMap | null>(null);
  const sdk = useRef<NaverMaps | null>(null);
  const marks = useRef<NMarker[]>([]);
  const alive = useRef(true);
  const [data, setData] = useState<MapItems | null>(null);
  const [pick, setPick] = useState<Card | null>(null);
  const [soldPick, setSoldPick] = useState<MapSold | null>(null);
  const [station, setStation] = useState<MapStation | null>(null);
  const [walk, setWalk] = useState(0);
  const [color, setColor] = useState<Color>("one");
  const [sold, setSold] = useState(false);
  const [narrow, setNarrow] = useState<Narrow[]>([]);
  const [zoom, setZoom] = useState(12);
  const [failed, setFailed] = useState(false);

  // 좁히기 조건 → 고른 역이 있으면 그 역에서 걸어서 N분 안 물건만
  const shown = useMemo(() => {
    const items = (data?.items ?? []).filter((c) => narrow.every((k) => KEEP[k](c)));
    const m = data?.walk_m;
    if (!station || !m) return items;
    return items.filter(
      (c) => c.lat != null && c.lon != null && nearM(c.lat, c.lon, station.lat, station.lon) <= m,
    );
  }, [data, station, narrow]);

  const load = useCallback(() => {
    const nm = map.current;
    if (!nm) return;
    setZoom(nm.getZoom());
    const b = nm.getBounds();
    const sw = b.getSW();
    const ne = b.getNE();
    fetchMapItems(window.location.search, [sw.lng(), sw.lat(), ne.lng(), ne.lat()])
      .then((d) => alive.current && setData(d))
      .catch(() => alive.current && setData({ total: 0, items: [], max: 0 }));
  }, []);

  // 점 그리기: 물건(묶음) → 낙찰 사례 → 역(물건 수)
  useEffect(() => {
    const m = sdk.current;
    const nm = map.current;
    if (!m || !nm || !data) return;
    marks.current.forEach((x) => x.setMap(null));
    const out: NMarker[] = cluster(shown, nm.getZoom()).map((g) => {
      const one = g.list.length === 1 ? g.list[0] : null;
      const html = one
        ? `<div class="mv-pin ${tone(one, color)}">${pinText(one, color)}</div>`
        : `<div class="mv-group">${g.list.length}</div>`;
      const mk = new m.Marker({
        position: new m.LatLng(g.lat, g.lon),
        map: nm,
        icon: { content: html, anchor: new m.Point(one ? 28 : 20, one ? 30 : 20) },
      });
      m.Event.addListener(mk, "click", () => {
        if (one) {
          setSoldPick(null);
          return setPick(one);
        }
        nm.morph(new m.LatLng(g.lat, g.lon), nm.getZoom() + 2); // 묶음은 눌러서 확대
      });
      return mk;
    });
    for (const s of data.sold ?? []) {
      const mk = new m.Marker({
        position: new m.LatLng(s.lat, s.lon),
        map: nm,
        icon: {
          content: `<div class="mv-sold">${t.soldPin(s.sale_rate)}</div>`,
          anchor: new m.Point(24, 12),
        },
      });
      m.Event.addListener(mk, "click", () => {
        setPick(null);
        setSoldPick(s);
      });
      out.push(mk);
    }
    // 역 이름은 가까이 봤을 때만(멀리서는 겹쳐서 못 읽음)
    for (const s of nm.getZoom() >= NAME_ZOOM ? (data.stations ?? []) : []) {
      const on = station?.name === s.name ? " on" : "";
      const mk = new m.Marker({
        position: new m.LatLng(s.lat, s.lon),
        map: nm,
        icon: {
          content: `<div class="mv-station${on}">${s.name}<b>${s.count}</b></div>`,
          anchor: new m.Point(30, 44),
        },
      });
      m.Event.addListener(mk, "click", () => {
        setPick(null);
        setSoldPick(null);
        setStation((cur) => (cur?.name === s.name ? null : s));
        if (nm.getZoom() < 15) nm.morph(new m.LatLng(s.lat, s.lon), 15);
      });
      out.push(mk);
    }
    marks.current = out;
  }, [data, shown, color, station]);

  useEffect(() => {
    alive.current = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const q = new URLSearchParams(window.location.search);
    const w = Number(q.get("walk"));
    if (WALKS.includes(w as (typeof WALKS)[number])) setWalk(w);
    const col = q.get("color") as Color;
    if (COLORS.includes(col)) setColor(col);
    if (q.get("sold")) setSold(true);
    const nr = (q.get("mf") ?? "").split(",").filter((k): k is Narrow => k in KEEP);
    if (nr.length) setNarrow(nr);
    void loadNaverMaps().then((m) => {
      if (!alive.current) return;
      if (!m || !box.current) return setFailed(true);
      sdk.current = m;
      const nm = new m.Map(box.current, {
        center: new m.LatLng(...SEOUL),
        zoom: 12,
        scaleControl: false,
        mapDataControl: false,
      });
      map.current = nm;
      // 지도를 멈추면 그 범위만 다시 받음(움직이는 중에는 기다림)
      m.Event.addListener(nm, "idle", () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(load, 250); // 손가락을 뗀 뒤 한 번만(끌 때마다 요청하지 않게)
      });
      // 처음 한 번은 바로 받음 — 네이버 지도가 처음 열릴 때 idle 을 안 알려 줘, 지도를 움직이기 전엔 비어 있었음(11/13)
      timer = setTimeout(load, 250);
    });
    return () => {
      alive.current = false;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  const pickWalk = (n: number) => {
    setWalk(n);
    setStation(null);
    setParam("walk", n ? String(n) : null);
    load();
  };
  const pickColor = (c: Color) => {
    const next = color === c ? "one" : c; // 다시 누르면 꺼짐(한 색)
    setColor(next);
    setParam("color", next === "one" ? null : next);
  };
  const toggleNarrow = (k: Narrow) => {
    const next = narrow.includes(k) ? narrow.filter((x) => x !== k) : [...narrow, k];
    setNarrow(next);
    setPick(null);
    setParam("mf", next.length ? next.join(",") : null);
  };
  const toggleSold = () => {
    setSold(!sold);
    setSoldPick(null);
    setParam("sold", sold ? null : "1");
    load();
  };

  return (
    <main className="page">
      <PageHeader title={t.title} back="/find" />
      {failed ? (
        <p className="sub">{t.noMap}</p>
      ) : (
        <>
          <div className="mv-tools">
            <div className="mv-row">
              <span className="mv-label">{t.narrowLabel}</span>
              <div className="pills" role="group" aria-label={t.narrowLabel}>
                {NARROW.map((k) => (
                  <button
                    key={k}
                    className={narrow.includes(k) ? "on" : ""}
                    aria-pressed={narrow.includes(k)}
                    onClick={() => toggleNarrow(k)}
                  >
                    {t.narrow[k]}
                  </button>
                ))}
              </div>
            </div>
            <div className="mv-row">
              <span className="mv-label">{t.layerLabel}</span>
              <label className="mv-check">
                <input
                  type="checkbox"
                  checked={walk > 0}
                  onChange={() => pickWalk(walk ? 0 : 10)}
                />
                {t.walkLabel}
              </label>
              {walk > 0 && (
                <div className="pills" role="group" aria-label={t.walkLabel}>
                  {WALKS.map((n) => (
                    <button key={n} className={walk === n ? "on" : ""} onClick={() => pickWalk(n)}>
                      {t.walkMin(n)}
                    </button>
                  ))}
                </div>
              )}
              <label className="mv-check">
                <input type="checkbox" checked={sold} onChange={toggleSold} />
                {t.sold}
              </label>
            </div>
            <div className="mv-row">
              <span className="mv-label">{t.colorLabel}</span>
              <div className="pills" role="group" aria-label={t.colorLabel}>
                {COLORS.map((c) => (
                  <button
                    key={c}
                    className={color === c ? "on" : ""}
                    aria-pressed={color === c}
                    onClick={() => pickColor(c)}
                  >
                    {t.color[c]}
                  </button>
                ))}
              </div>
              {LEGEND[color].map((k, i) => (
                <span key={k} className="mv-key">
                  <i className={`mv-dot ${k}`} aria-hidden="true" />
                  {t.legend[color][i]}
                </span>
              ))}
            </div>
            {walk > 0 && zoom < NAME_ZOOM && <p className="sub fs-sm m-0">{t.walkZoom}</p>}
          </div>
          <div className="mv-wrap">
            <div className="mv-mapbox">
              <div ref={box} className="mv-map" role="application" aria-label={t.title} />
            </div>
            <aside className="mv-side">
              {station ? (
                <div className="d-flex gap-8 f-wrap ai-center">
                  <strong>{t.stationPick(station.name, shown.length)}</strong>
                  <button className="link fs-sm" onClick={() => setStation(null)}>
                    {t.stationClear}
                  </button>
                </div>
              ) : (
                <div className="sub m-0">
                  {data
                    ? narrow.length
                      ? t.countNarrow(shown.length)
                      : t.count(data.items.length, data.total)
                    : t.loading}
                </div>
              )}
              {data && data.total > data.items.length && (
                <p className="sub fs-sm mt-4">{t.zoomIn}</p>
              )}
              {soldPick && (
                <div className="mv-pick mv-pick-sold">
                  <strong>{soldPick.building || soldPick.usage}</strong>
                  <div>{won(soldPick.winning_bid_krw)}</div>
                  <div className="sub fs-sm">
                    {t.soldLine(soldPick.sale_date, soldPick.sale_rate)}
                  </div>
                </div>
              )}
              {pick && (
                <div className="mv-pick">
                  <ItemCard c={pick} />
                </div>
              )}
              <div className="mv-list">
                {data && shown.length === 0 && <p className="sub mt-12">{t.empty}</p>}
                {shown
                  .filter((c) => c.item_id !== pick?.item_id)
                  .slice(0, 60)
                  .map((c) => (
                    <ItemCard key={c.item_id} c={c} />
                  ))}
              </div>
              <Link href="/find" className="link fs-sm mt-8 d-inline-block">
                {t.toFind}
              </Link>
            </aside>
          </div>
        </>
      )}
    </main>
  );
}
