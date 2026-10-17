"use client";

import { meApi } from "./api/me";

// 웹 푸시 구독: 서비스 워커 등록 → 브라우저 허락 → 구독 정보를 API에 저장.
function toBytes(base64: string): Uint8Array<ArrayBuffer> {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function subscribePush(token: string): Promise<"ok" | "denied" | "unsupported"> {
  const key = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  if (!key || !("serviceWorker" in navigator) || !("PushManager" in window)) return "unsupported";
  const reg = await navigator.serviceWorker.register("/sw.js");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return "denied";
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
