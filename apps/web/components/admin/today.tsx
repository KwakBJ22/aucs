"use client";

import { Delayed, SkRows } from "@/components/skeleton";
import { useEffect, useState } from "react";
import { adminApi, formatBytes, type Today } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { errText, useAdmin, when } from "./ctx";

const t = copy.admin;

// 1 오늘: 빨간 불 → 어제 숫자 → 아침 묶음 → DB·백업
export function TodayView({ go }: { go: (m: string) => void }) {
  const { token } = useAdmin();
  const [d, setD] = useState<Today | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    adminApi
      .today(token)
      .then(setD)
      .catch((e) => setErr(errText(e)));
  }, [token]);
  if (err) return <p className="adm-err">{err}</p>;
  if (!d)
    return (
      <Delayed>
        <SkRows n={6} />
      </Delayed>
    );
  const pct = d.db.used / d.db.limit;
  return (
    <>
      {d.red.length === 0 ? (
        <div className="adm-ok">{t.allOk}</div>
      ) : (
        d.red.map((r) => (
          <button key={r.text} className="adm-red" onClick={() => go(r.go)}>
            {r.text}
          </button>
        ))
      )}
      <section className="section">
        <h2>{t.yesterday}</h2>
        <div className="adm-nums">
          {t.yNames.map(([k, label]) => (
            <div key={k}>
              <b className="num">{(d.yesterday[k] ?? 0).toLocaleString("ko-KR")}</b>
              <span className="sub">{label}</span>
            </div>
          ))}
        </div>
        <p className="sub mt-8">{t.openLine(d.open.reports, d.open.inquiries)}</p>
      </section>
      {d.fill && (
        <section className="section">
          <h2>{t.fill.title}</h2>
          <div className="adm-nums">
            {(["registry", "appraisal"] as const).map((k) => (
              <div key={k}>
                <b className="num">
                  {d.fill?.watched ? Math.round(((d.fill[k] ?? 0) * 100) / d.fill.watched) : 0}%
                </b>
                <span className="sub">{t.fill[k]}</span>
              </div>
            ))}
            <div>
              <b className="num">{d.fill.members.toLocaleString("ko-KR")}</b>
              <span className="sub">{t.fill.members}</span>
            </div>
          </div>
          <p className="sub mt-8">{t.fill.line(d.fill.watched, d.fill.uploaders, d.fill.week)}</p>
        </section>
      )}
      <section className="section">
        <h2>{t.morning}</h2>
        {d.steps.length === 0 ? (
          <p className="sub">{t.morningNone}</p>
        ) : (
          d.steps.map((s) => (
            <div key={s.job_id} className="adm-row">
              <span>{s.name_ko}</span>
              <span
                className={`chip ${s.status === "ok" ? "green" : s.status === "running" ? "blue" : "orange"}`}
              >
                {t.statusName[s.status] ?? s.status}
              </span>
              <span className="sub num">{s.item_count?.toLocaleString("ko-KR") ?? "-"}</span>
            </div>
          ))
        )}
      </section>
      <section className="section">
        <h2>{t.db}</h2>
        <div className="adm-bar">
          <i
            className={pct > 0.8 ? "warn" : ""}
            style={{ width: `${Math.min(100, pct * 100)}%` }}
          />
        </div>
        <p className="sub mt-8">
          {formatBytes(d.db.used)} / {formatBytes(d.db.limit)}
        </p>
        <p className="sub">
          {t.backup}: {d.backup ? `${when(d.backup.at)} · ${d.backup.message ?? ""}` : t.never}
        </p>
        <p className="sub">
          {t.restore}:{" "}
          {d.restore ? `${when(d.restore.at)} · ${t.statusName[d.restore.status]}` : t.never}
        </p>
      </section>
    </>
  );
}
