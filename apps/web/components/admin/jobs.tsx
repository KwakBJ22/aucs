"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type ErrorRow, type Jobs } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { Confirm, errText, useAdmin, when } from "./ctx";

const t = copy.admin;

// 2 작업·수집: 작업별 마지막 실행 + 14일 모양, 다시 돌리기 요청, 오류 묶음
export function JobsView() {
  const { token, say, can } = useAdmin();
  const [d, setD] = useState<Jobs | null>(null);
  const [errs, setErrs] = useState<ErrorRow[]>([]);
  const [pick, setPick] = useState("daily");
  const load = useCallback(() => {
    adminApi
      .screen(token, "jobs")
      .then((x) => {
        setD(x.jobs);
        setErrs(x.errors);
      })
      .catch((e) => say(errText(e)));
  }, [token, say]);
  useEffect(load, [load]);
  if (!d) return <p className="sub">{t.loading}</p>;
  const op = can("operator");
  return (
    <>
      {op && (
        <section className="section">
          <h2>{t.request}</h2>
          <p className="sub">{t.requestNote}</p>
          <div className="adm-line mt-8">
            <select className="adm-input" value={pick} onChange={(e) => setPick(e.target.value)}>
              {Object.entries(d.requestable).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <button
              className="adm-btn primary"
              onClick={() =>
                adminApi
                  .requestJob(token, pick)
                  .then((r) => {
                    say(r.dup ? t.requestDup : t.requestOk);
                    load();
                  })
                  .catch((e) => say(errText(e)))
              }
            >
              {t.requestGo}
            </button>
            <Confirm
              label={t.markStale}
              ask={t.markStaleAsk}
              onYes={() =>
                adminApi
                  .markStale(token)
                  .then((r) => {
                    say(t.markStaleDone(r.n));
                    load();
                  })
                  .catch((e) => say(errText(e)))
              }
            />
          </div>
          {d.requests.slice(0, 5).map((r) => (
            <div key={r.req_id} className="adm-row sub">
              <span>{d.requestable[r.job_key] ?? r.job_key}</span>
              <span>{t.reqStatus[r.status] ?? r.status}</span>
              <span>{when(r.requested_at)}</span>
            </div>
          ))}
        </section>
      )}
      <section className="section">
        <h2>{t.jobs}</h2>
        {d.jobs.map((j) => (
          <details key={j.job_id} className="adm-job">
            <summary>
              <span className="adm-job-name">{j.name_ko}</span>
              <span className="adm-days">
                {Array.from({ length: 14 }, (_, i) => {
                  const day = new Date(Date.parse(d.first_day) + i * 864e5)
                    .toISOString()
                    .slice(0, 10);
                  const s = j.days.find((x) => x.day === day)?.s ?? "none";
                  return <i key={day} className={s} title={day} />;
                })}
              </span>
              <span
                className={`chip ${j.status === "ok" ? "green" : j.status ? "orange" : "gray"}`}
              >
                {j.status ? (t.statusName[j.status] ?? j.status) : t.never}
              </span>
            </summary>
            <p className="sub">
              {when(j.started_at)} ~ {when(j.finished_at)} ·{" "}
              {j.item_count?.toLocaleString("ko-KR") ?? "-"}
              {t.unit}
            </p>
            {j.message && <p className="sub adm-msg">{j.message}</p>}
          </details>
        ))}
      </section>
      <section className="section">
        <h2>{t.errors}</h2>
        {errs.length === 0 && <p className="sub">{t.none}</p>}
        {errs.map((e) => (
          <details key={`${e.side}-${e.message}`} className="adm-job">
            <summary>
              <b className="adm-red-text">{t.errorSide[e.side] ?? e.side}</b>
              <span className="ellipsis">{e.message}</span>
              <span className="sub">{t.errorLine(e.n, e.devices)}</span>
            </summary>
            <p className="sub">
              {e.path ?? ""} · {when(e.last_at)}
            </p>
            {e.stack && <pre className="adm-pre">{e.stack}</pre>}
            {op && (
              <button
                className="adm-btn"
                onClick={() =>
                  adminApi
                    .errorFixed(token, e.side, e.message)
                    .then(() => {
                      say(t.fixedOk);
                      load();
                    })
                    .catch((x) => say(errText(x)))
                }
              >
                {t.errorFix}
              </button>
            )}
          </details>
        ))}
      </section>
    </>
  );
}
