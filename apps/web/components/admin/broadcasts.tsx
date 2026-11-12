"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type Broadcast, type Target } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;
const b = copy.admin.bc;
const KINDS = ["all", "region", "paid", "free"] as const;

// 알림 보내기(11/12, 기능명세서 6): 대상 → 대상 수 → 바로/예약. 실제 보내기는 PC 5분 작업.
export function BroadcastView() {
  const { token, say, can } = useAdmin();
  const [rows, setRows] = useState<Broadcast[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [link, setLink] = useState("");
  const [kind, setKind] = useState<Target["kind"]>("all");
  const [regions, setRegions] = useState("");
  const [at, setAt] = useState(""); // 비우면 바로
  const [n, setN] = useState<{ users: number; push: number } | null>(null);
  const load = useCallback(() => {
    adminApi
      .broadcasts(token)
      .then(setRows)
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);

  const target = (): Target =>
    kind === "region"
      ? {
          kind,
          regions: regions
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
        }
      : { kind };
  const check = () =>
    adminApi
      .bcPreview(token, target())
      .then(setN)
      .catch((e) => say(errText(e)));
  const ready = title.trim().length >= 2 && n !== null && n.users > 0;

  return (
    <>
      {can("operator") && (
        <section className="section">
          <h2>{b.title}</h2>
          <p className="sub">{b.note}</p>
          <input
            className="adm-input w-full mt-8"
            placeholder={b.head}
            maxLength={60}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            className="adm-input w-full mt-8"
            rows={2}
            maxLength={300}
            placeholder={b.body}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <input
            className="adm-input w-full mt-8"
            placeholder={b.link}
            value={link}
            onChange={(e) => setLink(e.target.value.trim())}
          />
          <div className="adm-line">
            {KINDS.map((k) => (
              <button
                key={k}
                className={`adm-btn${kind === k ? " primary" : ""}`}
                onClick={() => {
                  setKind(k);
                  setN(null);
                }}
              >
                {b.target[k]}
              </button>
            ))}
          </div>
          {kind === "region" && (
            <input
              className="adm-input w-full mt-8"
              placeholder={b.regions}
              value={regions}
              onChange={(e) => {
                setRegions(e.target.value);
                setN(null);
              }}
            />
          )}
          <div className="adm-line">
            <label className="sub">
              {b.when}{" "}
              <input
                type="datetime-local"
                className="adm-input"
                value={at}
                onChange={(e) => setAt(e.target.value)}
              />
            </label>
            <span className="sub">{at ? b.at : b.now}</span>
          </div>
          <div className="adm-line">
            <button className="adm-btn" onClick={check}>
              {b.check}
            </button>
            {n && <span className="sub">{b.count(n.users, n.push)}</span>}
            {ready && (
              <Confirm
                label={b.go}
                ask={b.ask(n.users)}
                onYes={() =>
                  adminApi
                    .bcSend(token, {
                      title: title.trim(),
                      body: body.trim(),
                      link: link || null,
                      target: target(),
                      send_at: at ? `${at}:00+09:00` : null,
                    })
                    .then(() => {
                      say(b.sent);
                      setTitle("");
                      setBody("");
                      setLink("");
                      setAt("");
                      setN(null);
                      load();
                    })
                    .catch((e) => say(errText(e)))
                }
              />
            )}
          </div>
        </section>
      )}
      <section className="section">
        <h2>{b.list}</h2>
        {rows.length === 0 && <p className="sub">{t.none}</p>}
        {rows.map((r) => (
          <div key={r.bc_id} className="adm-card">
            <div>
              <b>{r.title}</b>{" "}
              <span
                className={`chip ${r.status === "sent" ? "green" : r.status === "waiting" ? "blue" : "gray"}`}
              >
                {b.status[r.status] ?? r.status}
              </span>
            </div>
            <div className="sub">
              {b.target[r.target.kind] ?? r.target.kind}
              {r.target.regions?.length ? ` (${r.target.regions.join(", ")})` : ""} ·{" "}
              {when(r.sent_at ?? r.send_at)}
              {r.sent_n !== null ? ` · ${b.sentN(r.sent_n)}` : ""}
            </div>
            {can("operator") && r.status === "waiting" && (
              <div className="adm-line">
                <Confirm
                  label={b.cancel}
                  ask={b.cancelAsk}
                  onYes={() =>
                    adminApi
                      .bcCancel(token, r.bc_id)
                      .then(load)
                      .catch((e) => say(errText(e)))
                  }
                />
              </div>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
