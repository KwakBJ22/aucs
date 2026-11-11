"use client";

import { useEffect, useRef, useState } from "react";
import { copy } from "@/lib/copy.ko";

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
