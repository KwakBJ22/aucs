"use client";

import { meApi } from "./api/me";
import { isStandalone, platform } from "./install";

// 웹 푸시 구독: 서비스 워커 등록 → 브라우저 허락 → 구독 정보를 API에 저장.
function toBytes(base64: string): Uint8Array<ArrayBuffer> {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

// 아이폰(11/8): 사파리 창에서는 알림이 안 되고 홈 화면에 둔 옥스에서만 됨 → "ios"로 따로 알림.
// 허락 창은 누른 순간 바로 띄워야 해서(그 사이 기다리면 아이폰이 막음) 서비스 워커 등록보다 먼저.
export async function subscribePush(
  token: string,
): Promise<"ok" | "denied" | "unsupported" | "ios"> {
  const key = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  const supported =
    "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (!supported) return platform() === "ios" && !isStandalone() ? "ios" : "unsupported";
  if (!key) return "unsupported";
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return "denied";
  await navigator.serviceWorker.register("/sw.js");
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: toBytes(key),
  });
  const json = sub.toJSON();
  await meApi.addPush(token, {
    endpoint: sub.endpoint,
    p256dh: json.keys?.p256dh ?? "",
    auth: json.keys?.auth ?? "",
  });
  return "ok";
}
