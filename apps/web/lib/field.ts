"use client";

// 현장 체크 사진·음성: Supabase 저장소 'field'(비공개), 경로 {user_id}/{물건}/{시각}.{확장자}
import { supabase } from "./auth";

const BUCKET = "field";
// 저장소 경로는 영문·숫자만 안전 — 「타경」을 K로
export const itemKey = (itemId: string) =>
  itemId.replace("타경", "K").replace(/[^A-Za-z0-9-]/g, "_");

export type FieldFile = {
  name: string;
  path: string;
  url: string;
  kind: "photo" | "voice";
  at: string;
};

export async function listFiles(uid: string, itemId: string): Promise<FieldFile[]> {
  if (!supabase) return [];
  const dir = `${uid}/${itemKey(itemId)}`;
  const { data, error } = await supabase.storage.from(BUCKET).list(dir, {
    sortBy: { column: "created_at", order: "desc" },
  });
  if (error || !data?.length) return [];
  const paths = data.map((f) => `${dir}/${f.name}`);
  const { data: signed } = await supabase.storage.from(BUCKET).createSignedUrls(paths, 3600);
  return data.map((f, i) => ({
    name: f.name,
    path: paths[i]!,
    url: signed?.[i]?.signedUrl ?? "",
    kind: /\.(webm|m4a|mp3|ogg)$/.test(f.name) ? "voice" : "photo",
    at: (f.created_at ?? "").slice(5, 16).replace("T", " "),
  }));
}

// 사진은 긴 변 1600px JPEG로 줄여서 올림(저장 공간·데이터 아끼기)
// 아이폰(11/8): 사진 방향(EXIF)을 따르게 하고, 줄이기에 실패하면(오래된 사파리 등) 원본을 그대로 올림
async function shrink(file: File): Promise<Blob> {
  try {
    return await shrinkImage(file);
  } catch {
    return file;
  }
}

async function shrinkImage(file: File): Promise<Blob> {
  const img = await createImageBitmap(file, {
    imageOrientation: "from-image",
  } as ImageBitmapOptions);
  const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
  const c = document.createElement("canvas");
  c.width = Math.round(img.width * scale);
  c.height = Math.round(img.height * scale);
  c.getContext("2d")?.drawImage(img, 0, 0, c.width, c.height);
  return await new Promise((ok) => c.toBlob((b) => ok(b ?? file), "image/jpeg", 0.82));
}

export async function uploadPhoto(uid: string, itemId: string, file: File): Promise<string | null> {
  if (!supabase) return "저장소 설정이 없어요";
  const blob = await shrink(file);
  const path = `${uid}/${itemKey(itemId)}/${Date.now()}.jpg`;
  const { error } = await supabase.storage
    .from(BUCKET)
    .upload(path, blob, { contentType: "image/jpeg" });
  return error ? error.message : null;
}

export async function uploadVoice(uid: string, itemId: string, blob: Blob): Promise<string | null> {
  if (!supabase) return "저장소 설정이 없어요";
  const type = blob.type.split(";")[0] || "audio/webm";
  const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
  const path = `${uid}/${itemKey(itemId)}/${Date.now()}.${ext}`;
  const { error } = await supabase.storage.from(BUCKET).upload(path, blob, { contentType: type });
  return error ? error.message : null;
}

export async function removeFile(path: string): Promise<void> {
  await supabase?.storage.from(BUCKET).remove([path]);
}

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
