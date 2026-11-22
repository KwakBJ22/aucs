// 여러 곳 도는 순서 + 네이버 지도 앱 길찾기 한 번에(11/23 대표님).
// 네이버 지도 앱 URL Scheme: nmap://route/car — 도착지 dlat · dlng(필수) + 경유지 v1~v5(최대 5곳) · appname 필수.
// 출발지를 비우면 앱이 현재 위치에서 출발(우리는 위치를 받지 않음). 앱은 넘긴 순서대로 안내 — 순서는 여기서 정함.
// https://guide.ncloud-docs.com/docs/application-maps-url-scheme-vpc
export const MAX_STOPS = 6; // 경유지 5 + 도착지 1

export type Stop = { id: string; name: string; lat: number; lon: number };

// 두 좌표 사이 거리(m)
export function meters(a: [number, number], b: [number, number]): number {
  const R = 6371000;
  const rad = (x: number) => (x * Math.PI) / 180;
  const dLat = rad(b[0] - a[0]);
  const dLon = rad(b[1] - a[1]);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)));
}

/** 가까운 곳부터: 출발점(휴대폰 위치, 없으면 첫 곳)에서 가장 가까운 곳 → 거기서 가장 가까운 곳 … */
export function nearestOrder(stops: Stop[], from?: [number, number] | null): Stop[] {
  const left = [...stops];
  const out: Stop[] = [];
  let at: [number, number] | null = from ?? null;
  if (!at && left.length) {
    const first = left.shift()!;
    out.push(first);
    at = [first.lat, first.lon];
  }
  while (left.length && at) {
    let best = 0;
    for (let i = 1; i < left.length; i++)
      if (meters(at, [left[i]!.lat, left[i]!.lon]) < meters(at, [left[best]!.lat, left[best]!.lon]))
        best = i;
    const s = left.splice(best, 1)[0]!;
    out.push(s);
    at = [s.lat, s.lon];
  }
  return out;
}

/** nmap://route/car?… (앞의 곳들은 경유지 v1~v5, 마지막 곳이 도착지). 6곳 넘으면 앞 6곳만. */
export function naverRoute(stops: Stop[], appname: string): string {
  const s = stops.slice(0, MAX_STOPS);
  const last = s[s.length - 1];
  if (!last) return "";
  // 이름은 encodeURIComponent(빈칸 %20 — URLSearchParams 의 「+」는 앱이 글자로 보일 수 있어 안 씀)
  const q: [string, string | number][] = [
    ["dlat", last.lat],
    ["dlng", last.lon],
    ["dname", last.name],
  ];
  s.slice(0, -1).forEach((x, i) => {
    q.push([`v${i + 1}lat`, x.lat], [`v${i + 1}lng`, x.lon], [`v${i + 1}name`, x.name]);
  });
  q.push(["appname", appname]);
  return `nmap://route/car?${q.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&")}`;
}

/** 안드로이드 웹은 intent 주소(앱이 없으면 플레이 스토어로 감 — 공식 문서 방식). */
export function androidIntent(nmap: string): string {
  return `${nmap.replace("nmap://", "intent://")}#Intent;scheme=nmap;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=com.nhn.android.nmap;end`;
}

export function isPhone(ua: string): "android" | "ios" | null {
  if (/Android/i.test(ua)) return "android";
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  return null;
}

/** 앱 열기. 아이폰은 앱이 없으면 아무 일도 없어서, 1.5초 뒤에도 이 화면이면 onMissing(문서 방식). */
export function openNaver(nmap: string, onMissing: () => void): void {
  const phone = isPhone(navigator.userAgent);
  if (phone === "android") {
    window.location.href = androidIntent(nmap);
    return;
  }
  const t = window.setTimeout(() => {
    if (document.visibilityState === "visible") onMissing();
  }, 1500);
  document.addEventListener("visibilitychange", () => window.clearTimeout(t), { once: true });
  window.location.href = nmap;
}
