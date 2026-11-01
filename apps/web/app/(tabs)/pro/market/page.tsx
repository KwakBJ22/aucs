"use client";

import { LoadError } from "@/components/load-error";
import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { fetchRegions, type RegionRow } from "@/lib/api/items";
import { fetchMarket, type Market } from "@/lib/api/pro";
import { OnbidMarket, StatTable } from "@/components/pro/market-parts";
import { useRouter, useSearchParams } from "next/navigation";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

const t = copy.proMarket;
const MIN_SCORE = 20; // 이보다 적으면 성적을 말하지 않음

function ProMarket() {
  const sp = useSearchParams();
  const router = useRouter();
  const onbid = sp.get("source") === "onbid";
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [usage, setUsage] = useState<string[]>([]);
  const [months, setMonths] = useState(3);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [m, setM] = useState<Market | null>(null);
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);

  useEffect(() => {
    fetchRegions()
      .then(setRegions)
      .catch(() => {});
  }, []);
  useEffect(() => {
    let stale = false;
    if (onbid) return;
    setFailed(false);
    fetchMarket({ sido: sido || undefined, sigungu: sigungu || undefined, usage, months })
      .then((r) => !stale && setM(r))
      .catch(() => !stale && setFailed(true)); // 예전엔 오류를 삼켜서 「불러오는 중」에 멈춰 있었음(11/1)
    return () => {
      stale = true;
    };
  }, [sido, sigungu, usage, months, onbid, tries]);

  const sel = {
    fontSize: 14,
    padding: "6px 8px",
    border: 0,
    borderRadius: 14,
    background: "var(--panel)",
    color: "var(--text)",
  };
  const sc = m?.scorecard;
  return (
    <main className="page pro-page">
      <PageHeader title={t.title} />
      {failed && !onbid && <LoadError onRetry={() => setTries((n) => n + 1)} />}
      <div className="pills mb-8" role="group">
        {(["court", "onbid"] as const).map((k) => (
          <button
            key={k}
            className={(k === "onbid") === onbid ? "on" : ""}
            onClick={() =>
              router.replace(k === "onbid" ? "/pro/market?source=onbid" : "/pro/market")
            }
          >
            {copy.find.source[k]}
          </button>
        ))}
      </div>
      {!onbid && (
        <nav className="seg mb-4">
          <a href="#region">{t.tabRegion}</a>
          <a href="#cases">{t.cases}</a>
          <a href="#score">{t.score}</a>
        </nav>
      )}
      <section className="section pro-filters">
        <div className="pro-row">
          <select
            value={sido}
            onChange={(e) => (setSido(e.target.value), setSigungu(""))}
            style={sel}
          >
            <option value="">{onbid ? t.onbidAllSido : copy.pro.allSido}</option>
            <option value="서울특별시">서울</option>
            <option value="경기도">경기</option>
          </select>
          <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} style={sel}>
            <option value="">{copy.pro.allSigungu}</option>
            {regions
              .filter((r) => !sido || r.sido === sido)
              .map((r) => (
                <option key={`${r.sido}${r.sigungu}`} value={r.sigungu}>
                  {r.sigungu}
                </option>
              ))}
          </select>
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} style={sel}>
            {[1, 3, 6, 12].map((x) => (
              <option key={x} value={x}>
                {t.months(x)}
              </option>
            ))}
          </select>
        </div>
        <div className="pro-row">
          <span className="sub">{copy.pro.usage}</span>
          {Object.entries(copy.pro.usages).map(([k, v]) => (
            <button
              key={k}
              className={`chip ${usage.includes(k) ? "green" : "gray"} b-0 mh-30`}

              onClick={() =>
                setUsage(usage.includes(k) ? usage.filter((x) => x !== k) : [...usage, k])
              }
            >
              {v}
            </button>
          ))}
        </div>
      </section>

      {onbid ? (
        <OnbidMarket sido={sido} sigungu={sigungu} usage={usage} months={months} />
      ) : (
        <>
          <section className="section q-sec" id="score">
            <h2 className="fs-base">{t.score}</h2>
            {!sc ? (
              <div className="sub">{copy.pro.loading}</div>
            ) : sc.n < MIN_SCORE ? (
              <div className="sub">{t.scoreWait(sc.n, MIN_SCORE)}</div>
            ) : (
              <div className="fs-base">
                {t.scoreLine(Math.round((sc.inside * 100) / sc.n), sc.n)}{" "}
                <span className="sub">
                  {t.scoreSplit(
                    Math.round((sc.below * 100) / sc.n),
                    Math.round((sc.above * 100) / sc.n),
                  )}
                </span>
              </div>
            )}
            <div className="sub mt-4">{t.scoreNote}</div>
            {m && m.misses.length > 0 && (
              <>
                <div className="fs-md fw-7 mt-12">{t.misses}</div>
                {m.misses.map((r) => (
                  <div key={`${r.court}${r.case_no}${r.sale_date}`} className="line-row fs-md">
                    <span>
                      {r.item_id ? (
                        <Link href={`/item/${encodeURIComponent(r.item_id)}`}>
                          {r.court} {r.case_no}
                        </Link>
                      ) : (
                        `${r.court} ${r.case_no}`
                      )}{" "}
                      <span className="sub">
                        {r.sale_date.slice(5)} · {r.address}
                      </span>
                    </span>
                    <span>
                      {t.missLine(Math.round(r.p25), Math.round(r.p75), Math.round(r.sale_rate))}
                    </span>
                  </div>
                ))}
              </>
            )}
          </section>

          {m && (
            <div className="pc-grid g-2x2 q-sec" id="region" style={{ rowGap: 12 }}>
              <StatTable
                title={t.byUsage}
                rows={m.by_usage.map((r) => ({
                  ...r,
                  label: copy.pro.usages[r.usage as keyof typeof copy.pro.usages] ?? t.etc,
                }))}
              />
              <StatTable
                title={t.byCourt}
                rows={m.by_court.map((r) => ({ ...r, label: r.court }))}
              />
              <StatTable
                title={t.byFailed}
                rows={m.by_failed.map((r) => ({ ...r, label: t.failed(r.failed) }))}
              />
              <StatTable
                title={t.byMonth}
                rows={m.by_month.map((r) => ({ ...r, label: r.month }))}
              />
            </div>
          )}

          <section className="section q-sec p-0 ox-auto mt-12" id="cases">
            <div className="pt-14 pb-0 px-14">
              <h2 className="fs-base">{t.cases}</h2>
            </div>
            <table className="pro-table">
              <thead>
                <tr>
                  {t.cols.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {m?.cases.map((r) => (
                  <tr key={`${r.court}${r.case_no}${r.sale_date}${r.address}`}>
                    <td>{r.sale_date.slice(5)}</td>
                    <td>
                      {r.item_id ? (
                        <Link href={`/item/${encodeURIComponent(r.item_id)}`}>
                          {r.court} {r.case_no}
                        </Link>
                      ) : (
                        `${r.court} ${r.case_no}`
                      )}
                    </td>
                    <td>{r.usage_name}</td>
                    <td>{r.address}</td>
                    <td>{r.building_area_m2 ? `${Math.round(r.building_area_m2)}㎡` : ""}</td>
                    <td>{won(r.appraisal_krw)}</td>
                    <td>{won(r.winning_bid_krw)}</td>
                    <td>
                      <b>{Math.round(r.sale_rate)}%</b>
                    </td>
                    <td>{r.failed_count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <div className="sub mt-8">{t.note}</div>
        </>
      )}
    </main>
  );
}

export default function ProMarketPage() {
  return (
    <Suspense>
      <ProMarket />
    </Suspense>
  );
}
