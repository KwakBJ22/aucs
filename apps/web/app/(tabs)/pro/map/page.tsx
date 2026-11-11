"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { PageHeader } from "@/components/layout/page-header";
import { fetchMapItems, type ItemCard as Card, type MapItems } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { wonShort } from "@/lib/format";
import { loadNaverMaps, type NMap, type NMarker, type NaverMaps } from "@/lib/naver-map";

const t = copy.mapView;
const SEOUL: [number, number] = [37.5665, 126.978];

// 점 색(11/12): 걸린 위험이 크면 빨강 · 유찰된 것 주황 · 신건 파랑
function tone(c: Card): string {
  const lv = c.top_signal?.level;
  if (lv === "fatal" || lv === "high") return "red";
  if (c.failed_count) return "orange";
  return "blue";
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

// 지도 분석(11/12 대표님): 찾기 조건 그대로 · 보이는 범위의 물건만 받아 점으로, 오른쪽(휴대폰은 아래) 목록
export default function MapPage() {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<NMap | null>(null);
  const sdk = useRef<NaverMaps | null>(null);
  const marks = useRef<NMarker[]>([]);
  const [data, setData] = useState<MapItems | null>(null);
  const [pick, setPick] = useState<Card | null>(null);
  const [failed, setFailed] = useState(false);

  const draw = useCallback((d: MapItems) => {
    const m = sdk.current;
    const nm = map.current;
    if (!m || !nm) return;
    marks.current.forEach((x) => x.setMap(null));
    marks.current = cluster(d.items, nm.getZoom()).map((g) => {
      const one = g.list.length === 1 ? g.list[0] : null;
      const html = one
        ? `<div class="mv-pin ${tone(one)}">${wonShort(one.min_price_krw)}</div>`
        : `<div class="mv-group">${g.list.length}</div>`;
      const mk = new m.Marker({
        position: new m.LatLng(g.lat, g.lon),
        map: nm,
        icon: { content: html, anchor: new m.Point(one ? 28 : 20, one ? 30 : 20) },
      });
      m.Event.addListener(mk, "click", () => {
        if (one) return setPick(one);
        nm.morph(new m.LatLng(g.lat, g.lon), nm.getZoom() + 2); // 묶음은 눌러서 확대
      });
      return mk;
    });
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    void loadNaverMaps().then((m) => {
      if (!alive) return;
      if (!m || !box.current) return setFailed(true);
      sdk.current = m;
      const nm = new m.Map(box.current, {
        center: new m.LatLng(...SEOUL),
        zoom: 12,
        scaleControl: false,
        mapDataControl: false,
      });
      map.current = nm;
      const query = window.location.search;
      // 지도를 멈추면 그 범위만 다시 받음(움직이는 중에는 기다림)
      m.Event.addListener(nm, "idle", () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          const b = nm.getBounds();
          const sw = b.getSW();
          const ne = b.getNE();
          fetchMapItems(query, [sw.lng(), sw.lat(), ne.lng(), ne.lat()])
            .then((d) => {
              if (!alive) return;
              setData(d);
              draw(d);
            })
            .catch(() => alive && setData({ total: 0, items: [], max: 0 }));
        }, 250); // 손가락을 뗀 뒤 한 번만(끌 때마다 요청하지 않게)
      });
    });
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [draw]);

  return (
    <main className="page">
      <PageHeader title={t.title} back="/find" />
      {failed ? (
        <p className="sub">{t.noMap}</p>
      ) : (
        <div className="mv-wrap">
          <div ref={box} className="mv-map" role="application" aria-label={t.title} />
          <aside className="mv-side">
            <div className="sub m-0">
              {data ? t.count(data.items.length, data.total) : t.loading}
            </div>
            {data && data.total > data.items.length && <p className="sub fs-sm mt-4">{t.zoomIn}</p>}
            {pick && (
              <div className="mv-pick">
                <ItemCard c={pick} />
              </div>
            )}
            <div className="mv-list">
              {data?.items.length === 0 && <p className="sub mt-12">{t.empty}</p>}
              {data?.items
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
      )}
    </main>
  );
}
