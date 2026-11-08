"use client";

import { SkListPage } from "@/components/skeleton";
import { copyText } from "@/lib/copy-text";
import { PageHeader } from "@/components/layout/page-header";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { NeedLogin } from "@/components/need-login";
import type { ItemDetail } from "@/lib/api/items";
import { meApi, type Workspace } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import {
  listFiles,
  meters,
  removeFile,
  uploadPhoto,
  uploadVoice,
  type FieldFile,
} from "@/lib/field";

const t = copy.field;

// 현장 체크(FIELD-02): 가까이 왔는지 · 관리사무소에 물어볼 것 · 현장에서 볼 것 · 사진·음성
export default function FieldPage() {
  const id = decodeURIComponent(String(useParams().id));
  const { session, ready } = useSession();
  const token = session?.access_token ?? null;
  const uid = session?.user.id ?? null;
  const [d, setD] = useState<ItemDetail | null>(null);
  const [w, setW] = useState<Workspace | null>(null);
  const [files, setFiles] = useState<FieldFile[]>([]);
  const [dist, setDist] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [copied, setCopied] = useState(false);
  const photoInput = useRef<HTMLInputElement>(null);

  const reload = useCallback(() => {
    if (uid) listFiles(uid, id).then(setFiles);
  }, [uid, id]);
  useEffect(() => {
    if (!token) return;
    // 물건 상세 + 내 작업 공간을 한 번에(11/3 — 예전 2번)
    meApi
      .panel(token, id)
      .then((x) => {
        setD(x.d);
        setW(x.w);
      })
      .catch(() => setW(null));
    reload();
  }, [token, id, reload]);
  // 위치를 허락했으면 물건까지 거리를 보여 줌(저장하지 않음)
  useEffect(() => {
    if (!d?.lat || !d?.lon || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (p) => setDist(meters([p.coords.latitude, p.coords.longitude], [d.lat!, d.lon!])),
      () => {},
      { maximumAge: 60000, timeout: 8000 },
    );
  }, [d]);

  if (!ready)
    return (
      <main className="page">
        <SkListPage cards={false} />
      </main>
    );
  if (!session || !token || !uid) return <NeedLogin title={t.title} />;

  const toggle = (key: string) => {
    if (!w) return;
    const on = !w.checks[key];
    const checks = { ...w.checks };
    if (on) checks[key] = new Date().toISOString().slice(0, 10);
    else delete checks[key];
    setW({ ...w, checks });
    meApi.check(token, id, key, on).catch(() => {});
  };
  const onPhotos = async (list: FileList | null) => {
    if (!list?.length) return;
    setBusy(t.uploading);
    for (const f of Array.from(list)) {
      const err = await uploadPhoto(uid, id, f);
      if (err) setBusy(t.failed(err));
    }
    setBusy("");
    reload();
  };
  const startRec = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((x) => x.stop());
        setBusy(t.uploading);
        const err = await uploadVoice(uid, id, new Blob(chunks, { type: r.mimeType }));
        setBusy(err ? t.failed(err) : "");
        reload();
      };
      r.start();
      setRec(r);
    } catch {
      setBusy(t.noMic);
    }
  };
  const stopRec = () => {
    rec?.stop();
    setRec(null);
  };
  const del = async (f: FieldFile) => {
    setFiles((l) => l.filter((x) => x.path !== f.path));
    await removeFile(f.path);
  };
  const name = d?.building?.split(" ")[0] ?? "";
  const mapQ = (q: string) => `https://map.kakao.com/?q=${encodeURIComponent(q)}`;
  const askText = t.ask.join("\n");

  return (
    <main className="page">
      <PageHeader title={t.title} back={`/watch/${encodeURIComponent(id)}`} />
      <div className="pc-grid g-55-45">
        <div>
          {d && (
            <section className="section">
              <div className="fw-6">
                {d.place} {d.building ?? d.usage}
              </div>
              <div className="sub">{d.address}</div>
              {dist != null && (
                <div
                  className="mt-6 fw-7"
                  style={{ color: dist < 300 ? "var(--green)" : "var(--muted)" }}
                >
                  {dist < 300
                    ? t.near
                    : t.far(dist >= 1000 ? `${(dist / 1000).toFixed(1)}km` : `${dist}m`)}
                </div>
              )}
              <div className="d-flex gap-6 mt-10 f-wrap">
                {d.address && (
                  <a
                    href={mapQ(d.address)}
                    target="_blank"
                    rel="noreferrer"
                    className="chip gray mh-36"
                  >
                    {t.route} ›
                  </a>
                )}
                {name && (
                  <a
                    href={mapQ(`${name} 관리사무소`)}
                    target="_blank"
                    rel="noreferrer"
                    className="chip gray mh-36"
                  >
                    {t.office} ›
                  </a>
                )}
              </div>
            </section>
          )}

          <section className="section">
            <h2>{t.askTitle}</h2>
            {t.ask.map((q) => (
              <div key={q} className="fs-md py-6 px-0">
                {q}
              </div>
            ))}
            <button
              className="chip gray b-0 mh-36 mt-8"
              onClick={() =>
                void copyText(askText).then(() => {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                })
              }
            >
              {copied ? t.copied : t.copy}
            </button>
          </section>

          <section className="section">
            <h2>{t.lookTitle}</h2>
            {t.look.map(([k, label, sub]) => {
              const key = `field_${k}`;
              const on = Boolean(w?.checks[key]);
              return (
                <label key={k} className="d-flex gap-10 py-10 px-0 mh-44">
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => toggle(key)}
                    style={{ width: 20, height: 20 }}
                  />
                  <span>
                    <span className="fw-6" style={{ opacity: on ? 0.5 : 1 }}>
                      {label}
                    </span>
                    <span className="sub d-block">{sub}</span>
                  </span>
                </label>
              );
            })}
          </section>
        </div>
        <div>
          <section className="section">
            <h2>{t.media}</h2>
            <div className="d-flex gap-8 f-wrap">
              <button
                className="btn primary f-1"
                style={{ height: 48 }}
                onClick={() => photoInput.current?.click()}
              >
                {t.photo}
              </button>
              <button
                className="btn f-1"
                style={{
                  height: 48,
                  background: rec ? "var(--red)" : "var(--gray-chip)",
                  color: rec ? "#fff" : "var(--text)",
                }}
                onClick={rec ? stopRec : startRec}
              >
                {rec ? t.stop : t.voice}
              </button>
            </div>
            <input
              ref={photoInput}
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              hidden
              onChange={(e) => {
                void onPhotos(e.target.files);
                e.target.value = "";
              }}
            />
            {busy && <div className="sub mt-6">{busy}</div>}
            <div className="field-grid">
              {files.map((f) =>
                f.kind === "photo" ? (
                  <div key={f.path} className="field-item">
                    <a href={f.url} target="_blank" rel="noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={f.url} alt={f.at} />
                    </a>
                    <button onClick={() => del(f)} aria-label={t.remove}>
                      ×
                    </button>
                  </div>
                ) : (
                  <div key={f.path} className="field-voice">
                    <audio controls src={f.url} />
                    <span className="sub">{f.at}</span>
                    <button className="chip gray b-0" onClick={() => del(f)}>
                      {t.remove}
                    </button>
                  </div>
                ),
              )}
            </div>
            <div className="sub mt-6">{t.private}</div>
          </section>
        </div>
      </div>
    </main>
  );
}
