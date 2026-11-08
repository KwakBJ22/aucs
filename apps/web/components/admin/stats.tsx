"use client";

import { Delayed, SkRows } from "@/components/skeleton";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { adminApi, type Metrics, type Stats } from "@/lib/api/admin";
import { copy } from "@/lib/copy.ko";
import { errText, useAdmin } from "./ctx";

const t = copy.admin;
const COLS = ["devices", "views", "watched", "new_users"] as const;

// 7 통계: 성공 지표(7일) · 주별 추이(12주) · 많이 본 물건(기간 고르기) · CSV 받기
export function StatsView() {
  const { token, say } = useAdmin();
  const [m, setM] = useState<Metrics | null>(null);
  const [s, setS] = useState<Stats | null>(null);
  const [days, setDays] = useState(30);
  // 처음엔 성공 지표·주별 추이·많이 본 물건을 한 번에, 기간을 바꾸면 많이 본 물건만 다시(11/3)
  useEffect(() => {
    adminApi
      .screen(token, "stats", 30)
      .then((x) => {
        setM(x.status.metrics ?? null);
        setS(x.stats);
      })
      .catch((e) => say(errText(e)));
  }, [token, say]);
  const lastDays = useRef(days);
  useEffect(() => {
    if (lastDays.current === days) return; // 처음 30일은 위에서 받음(개발 모드에서 두 번 돌아도 안전)
    lastDays.current = days;
    adminApi
      .stats(token, days)
      .then(setS)
      .catch((e) => say(errText(e)));
  }, [token, days, say]);

  const csv = () => {
    if (!s) return;
    const lines = [
      ["주", ...COLS.map((k) => t.weekCols[k])].join(","),
      ...s.weeks.map((w) => [w.wk, ...COLS.map((k) => w[k])].join(",")),
      "",
      `${t.topItems} (${days}일),상세,기기,주소`,
      ...s.top.map((x) =>
        [x.item_id, x.views, x.devices, `"${(x.address ?? "").replace(/"/g, "'")}"`].join(","),
      ),
    ];
    const url = URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `oks-stats-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <section className="section">
        <h2>{t.metrics}</h2>
        {m ? (
          <ul className="pl-18">
            {t.metricRows(m).map((line) => (
              <li key={line} className="mt-8">
                {line}
              </li>
            ))}
          </ul>
        ) : (
          <Delayed>
            <SkRows n={5} />
          </Delayed>
        )}
      </section>
      {s && (
        <>
          <section className="section">
            <div className="adm-row">
              <h2>{t.weekly}</h2>
              <button className="adm-btn" onClick={csv}>
                {t.csv}
              </button>
            </div>
            {COLS.map((k) => {
              const max = Math.max(1, ...s.weeks.map((w) => w[k]));
              return (
                <div key={k} className="mt-8">
                  <div className="sub">{t.weekCols[k]}</div>
                  <div className="adm-week">
                    {s.weeks.map((w) => (
                      <i
                        key={w.wk}
                        title={`${w.wk} · ${w[k]}`}
                        style={{ height: `${(w[k] / max) * 100}%` }}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
            <div className="adm-row sub">
              <span>{s.weeks[0]?.wk}</span>
              <span>{s.weeks[s.weeks.length - 1]?.wk}</span>
            </div>
          </section>
          <section className="section">
            <div className="adm-row">
              <h2>{t.topItems}</h2>
              <div className="adm-tabs">
                {t.periods.map((d) => (
                  <button key={d} className={days === d ? "on" : ""} onClick={() => setDays(d)}>
                    {t.periodName(d)}
                  </button>
                ))}
              </div>
            </div>
            {s.top.length === 0 && <p className="sub">{t.none}</p>}
            {s.top.map((x) => (
              <div key={x.item_id} className="adm-card">
                <Link href={`/item/${encodeURIComponent(x.item_id)}`} target="_blank">
                  {x.address ?? x.item_id}
                </Link>
                <span className="sub">
                  {t.viewsLine(x.views, x.devices)}
                  {x.sale_date ? ` · ${x.sale_date}` : ""}
                </span>
              </div>
            ))}
          </section>
        </>
      )}
    </>
  );
}
