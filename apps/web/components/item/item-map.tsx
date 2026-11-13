"use client";

import { useEffect, useRef, useState } from "react";
import { copy } from "@/lib/copy.ko";
import type { ItemDetail } from "@/lib/api/items";

type ItemStation = NonNullable<ItemDetail["stations"]>[number];

import { loadNaverMaps as loadSdk, NAVER_KEY as KEY } from "@/lib/naver-map";

// 네이버 지도(11/11 대표님): 물건 위치 한 점. 키가 없거나 못 불러오면 지도 대신 「네이버 지도에서 보기」만
export function ItemMap({
  lat,
  lon,
  address,
}: {
  lat: number | null;
  lon: number | null;
  address: string | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(!KEY || lat == null || lon == null);
  const c = copy.map;

  useEffect(() => {
    if (failed || lat == null || lon == null) return;
    let alive = true;
    void loadSdk().then((m) => {
      if (!alive) return;
      if (!m || !box.current) return setFailed(true);
      const at = new m.LatLng(lat, lon);
      const map = new m.Map(box.current, {
        center: at,
        zoom: 16,
        scaleControl: false,
        mapDataControl: false,
      });
      new m.Marker({ position: at, map });
    });
    return () => {
      alive = false;
    };
  }, [failed, lat, lon]);

  const q = encodeURIComponent(address ?? "");
  const link = address ? (
    <a
      className="link fs-sm"
      href={`https://map.naver.com/p/search/${q}`}
      target="_blank"
      rel="noreferrer"
    >
      {c.openNaver}
    </a>
  ) : null;
  if (failed) return link ? <div className="mt-8">{link}</div> : null;
  return (
    <div className="mt-10">
      <div ref={box} className="item-map" role="img" aria-label={c.label} />
      <div className="mt-4">{link}</div>
    </div>
  );
}

// 휴대폰은 네이버 지도 앱 도보 길찾기(안드로이드는 앱 없으면 플레이스토어), PC 는 네이버 지도 웹에서 역 찾기(11/12)
function walkHref(
  from: { lat: number; lon: number },
  to: { lat: number; lon: number; name: string },
) {
  const q = new URLSearchParams({
    slat: String(from.lat),
    slng: String(from.lon),
    sname: "물건",
    dlat: String(to.lat),
    dlng: String(to.lon),
    dname: to.name,
    appname: "https://aucs.co.kr",
  }).toString();
  const ua = navigator.userAgent;
  if (/android/i.test(ua))
    return `intent://route/walk?${q}#Intent;scheme=nmap;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=com.nhn.android.nmap;end`;
  if (/iphone|ipad|ipod/i.test(ua)) return `nmap://route/walk?${q}`;
  return `https://map.naver.com/p/search/${encodeURIComponent(to.name)}`;
}

// 입지(11/13): 한 줄 → 가까운 역 세 곳(등급 · 도보 어림 WALK-01 · 네이버 지도 길찾기) → 주요 업무지구 → 가까운 정비사업
export function Stations({
  d,
}: {
  d: {
    lat: number | null;
    lon: number | null;
    stations?: ItemStation[];
    location?: ItemDetail["location"];
  };
}) {
  const w = copy.walk;
  if (!d.stations?.length || d.lat == null || d.lon == null) return null;
  const from = { lat: d.lat, lon: d.lon };
  const loc = d.location;
  return (
    <div className="mt-10">
      {loc?.line && <p className="fw-6 m-0 mb-8">{loc.line}</p>}
      {loc?.inside && (
        <p className="m-0 mb-8">
          <span className="chip orange">{loc.inside.label}</span>{" "}
          <span className="fs-sm">
            {[loc.inside.name, loc.inside.stage].filter(Boolean).join(" · ")}
          </span>
          <span className="sub fs-xs d-block mt-4">{w.insideNote[loc.inside.kind]}</span>
        </p>
      )}
      <div className="sub m-0">
        {w.title} {loc?.grade && <span className="chip blue">{loc.grade}</span>}
      </div>
      {d.stations.map((s) => (
        <div key={s.name} className="d-flex jc-between ai-center gap-8 mt-6">
          <span className="minw-0">
            <b className="fs-md">{s.name}</b>{" "}
            <span className="fs-xs c-muted">{s.lines.join(" · ")}</span>
            <span className="d-block fs-sm">{w.line(s.walk_min, s.walk_m)}</span>
          </span>
          <a
            className="link fs-sm nowrap"
            href="https://map.naver.com"
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              e.currentTarget.href = walkHref(from, s);
            }}
          >
            {w.route}
          </a>
        </div>
      ))}
      <p className="sub fs-xs mt-6 mb-0">{w.note}</p>
      {!!loc?.hubs.length && (
        <>
          <div className="sub mt-14 mb-0">{w.hubs}</div>
          {loc.hubs.map((h) => (
            <div key={h.name} className="d-flex jc-between ai-center gap-8 mt-6">
              <span>
                <b>{h.name}</b> <span className="fs-sm">{w.straight(h.straight_m)}</span>
              </span>
              {h.direct && <span className="chip green">{w.direct(h.direct)}</span>}
            </div>
          ))}
        </>
      )}
      {!!loc?.redev.length && (
        <>
          <div className="sub mt-14 mb-0">{w.redev}</div>
          {loc.redev.map((z) => (
            <div key={z.name} className="d-flex jc-between ai-center gap-8 mt-6">
              <span className="minw-0">
                <b>{z.name}</b>
                <span className="d-block fs-sm c-muted">
                  {[z.biz_type, z.stage].filter(Boolean).join(" · ")}
                </span>
              </span>
              <span className="fs-sm nowrap">{w.straight(z.straight_m)}</span>
            </div>
          ))}
          <p className="sub fs-xs mt-6 mb-0">{w.redevNote}</p>
        </>
      )}
    </div>
  );
}
