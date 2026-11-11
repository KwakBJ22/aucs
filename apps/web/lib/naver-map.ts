"use client";

// 네이버 지도 SDK 한 곳(11/11 물건 위치 · 11/12 지도 분석이 같이 씀). 키는 NEXT_PUBLIC_NAVER_MAP_KEY_ID.
export const NAVER_KEY = process.env.NEXT_PUBLIC_NAVER_MAP_KEY_ID ?? "";
const SDK = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${NAVER_KEY}`;

export type LatLng = { lat(): number; lng(): number };
export type NMap = {
  getBounds(): { getSW(): LatLng; getNE(): LatLng };
  getZoom(): number;
  setCenter(p: unknown): void;
  setZoom(z: number, effect?: boolean): void;
  morph(p: unknown, z: number): void;
};
export type NMarker = { setMap(m: NMap | null): void };
export type NaverMaps = {
  Map: new (el: HTMLElement, o: Record<string, unknown>) => NMap;
  LatLng: new (lat: number, lon: number) => LatLng;
  Point: new (x: number, y: number) => unknown;
  Marker: new (o: Record<string, unknown>) => NMarker;
  Event: { addListener(t: unknown, ev: string, fn: () => void): unknown };
};
declare global {
  interface Window {
    naver?: { maps?: NaverMaps };
  }
}

let loading: Promise<NaverMaps | null> | null = null;
export function loadNaverMaps(): Promise<NaverMaps | null> {
  if (!NAVER_KEY) return Promise.resolve(null);
  if (window.naver?.maps) return Promise.resolve(window.naver.maps);
  loading ??= new Promise((resolve) => {
    const s = document.createElement("script");
    s.src = SDK;
    s.async = true;
    s.onload = () => resolve(window.naver?.maps ?? null);
    s.onerror = () => {
      loading = null;
      resolve(null);
    };
    document.head.appendChild(s);
  });
  return loading;
}
