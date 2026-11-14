"use client";

import { parseTime } from "@/lib/format";
import { Delayed, SkRows } from "@/components/skeleton";
import { useCallback, useEffect, useState } from "react";
import { adminApi, formatBytes, type JobRun, type Today } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;
const tt = t.today;
const hm = (s: string | null | undefined) =>
  s
    ? parseTime(s).toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "";
const tone = (s: string) => (s === "ok" ? "green" : s === "running" ? "blue" : "orange");

function Chip({ status }: { status: string }) {
  return <span className={`chip ${tone(status)}`}>{t.statusName[status] ?? status}</span>;
}

// 1 오늘(11/14): 하실 일(눌러야 끝나는 것만) → 수집·분석 → 서비스 현황 → DB·백업
export function TodayView({ go }: { go: (m: string) => void }) {
  const { token, say, can } = useAdmin();
  const [d, setD] = useState<Today | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    adminApi
      .today(token)
      .then(setD)
      .catch((e) => setErr(errText(e)));
  }, [token]);
  useEffect(load, [load]);
  if (err) return <p className="adm-err">{err}</p>;
  if (!d)
    return (
      <Delayed>
        <SkRows n={6} />
      </Delayed>
    );
  const pct = d.db.used / d.db.limit;
  const { morning, morning_total, hourly, picks } = d.collect;
  const okN = morning.filter((s) => s.status === "ok").length;
  const first = morning[0];
  const lastEnd = morning
    .map((s) => s.finished_at)
    .filter(Boolean)
    .sort()
    .pop();
  const span = first ? `${hm(first.started_at)}~${hm(lastEnd)}` : "";
  const w = d.fill?.watched ?? 0;
  const rate = (n: number | undefined) => (w ? Math.round(((n ?? 0) * 100) / w) : 0);
  const op = can("operator");
  return (
    <>
      <section className="section">
        <h2>{tt.todo(d.todo.length)}</h2>
        {d.todo.length === 0 && <div className="adm-ok">{tt.todoNone}</div>}
        {d.todo.map((x) => (
          <div key={x.key} className={`adm-todo${x.red ? " red" : ""}`}>
            <button className="adm-todo-go" onClick={() => go(x.go)}>
              {x.text} ›
            </button>
            {op && x.ack_job && (
              <Confirm
                label={tt.ack}
                ask={tt.ackAsk}
                onYes={() =>
                  adminApi
                    .ackJob(token, x.ack_job as string)
                    .then(() => {
                      say(tt.acked);
                      load();
                    })
                    .catch((e) => say(errText(e)))
                }
              />
            )}
          </div>
        ))}
      </section>
      <section className="section">
        <h2>{tt.collect}</h2>
        <details className="adm-job">
          <summary>
            <span className="adm-job-name">{tt.morning}</span>
            <span className="sub num">{span}</span>
            {morning.length === 0 ? (
              <span className="chip gray">{tt.morningNone}</span>
            ) : (
              <span className={`chip ${okN === morning_total ? "green" : "orange"}`}>
                {tt.morningLine(okN, morning_total)}
              </span>
            )}
          </summary>
          {morning.map((s: JobRun) => (
            <div key={s.job_id} className="adm-row sub">
              <span>{s.name_ko}</span>
              <span className="num">
                {s.item_count?.toLocaleString("ko-KR") ?? "-"}
                {t.unit}
              </span>
              <Chip status={s.status} />
            </div>
          ))}
        </details>
        {hourly && (
          <div className="adm-row">
            <span className="adm-job-name">{hourly.name_ko}</span>
            <span className="sub num">{when(hourly.started_at)}</span>
            <Chip status={hourly.status} />
          </div>
        )}
        <div className="adm-row">
          <span className="adm-job-name">{tt.picks}</span>
          <span className="sub num">{when(picks.at)}</span>
          <span className={`chip ${picks.at && !picks.stale ? "green" : "orange"}`}>
            {!picks.at ? tt.picksNone : picks.stale ? tt.picksOld : t.statusName.ok}
          </span>
        </div>
      </section>
      <section className="section">
        <h2>{tt.service}</h2>
        <div className="adm-nums">
          {tt.nums.map(([k, label]) => (
            <div key={k}>
              <b className="num">{(d.service[k] ?? 0).toLocaleString("ko-KR")}</b>
              <span className="sub">{label}</span>
            </div>
          ))}
        </div>
        {d.fill && (
          <>
            <p className="sub mt-8">{tt.fill(rate(d.fill.registry), rate(d.fill.appraisal), w)}</p>
            <p className="sub">{tt.members(d.fill.members, d.fill.uploaders, d.fill.week)}</p>
          </>
        )}
        <p className="sub">{tt.academy(d.service.academy.users, d.service.academy.lessons)}</p>
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
