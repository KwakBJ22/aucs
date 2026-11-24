"use client";

import { copy } from "@/lib/copy.ko";
import { CalcBox, Row } from "@/components/calc-box";
import type { ItemDetail, Question } from "@/lib/api/items";
import { won } from "@/lib/format";
import { BuildingRows, ComplexBlock } from "@/components/item/building";
import { CheckBody } from "@/components/item/checklist";
import { AppraisalPoints, OriginalLink } from "@/components/item/appraisal";
import { ItemMap, Stations } from "@/components/item/item-map";
import { FailMobile } from "@/components/item/failure";
import { RegistryBox, HoldDocLink } from "@/components/item/registry";
import { Panel, t } from "@/components/item/shared";
import { useIsPc } from "@/lib/use-pc";
import { GoLinks } from "@/components/item/go-links";
import { useState } from "react";
import Link from "next/link";

const TENANTS_FIRST = 5;
const FAIL_CHIP: Record<string, string> = {
  걸림: "red",
  "확인 필요": "orange",
  확인함: "green",
  대비됨: "blue",
  "해당 없음": "gray",
};

// 임차인(11/11 대표님 — 32명을 다 늘어놓지 않음): 명수 한 줄 + 처음 5명, 나머지는 「모두 보기」
function Tenants({ list }: { list: Record<string, string | number | null>[] }) {
  const [all, setAll] = useState(false);
  if (!list.length) return null;
  const rows = all ? list : list.slice(0, TENANTS_FIRST);
  return (
    <>
      {list.length > TENANTS_FIRST && (
        <div className="fs-md fw-6 mb-4">{t.tenantsCount(list.length)}</div>
      )}
      {rows.map((x, i) => (
        <div key={i} className="py-6 px-0 fs-md">
          <b>{x.name ?? "임차인"}</b> {x.part ?? ""}
          <div className="sub m-0">
            {[
              x.move_in && `${t.moveIn} ${x.move_in}`,
              x.fixed && `${t.fixed} ${x.fixed}`,
              x.claim && `${t.claim} ${x.claim}`,
              x.deposit_krw && `보증금 ${won(Number(x.deposit_krw))}`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </div>
        </div>
      ))}
      {list.length > TENANTS_FIRST && (
        <button
          className="cond-row fold bg-bg mt-6"
          aria-expanded={all}
          onClick={() => setAll(!all)}
        >
          <span className="fs-md">
            {all ? t.tenantsLess : t.tenantsMore(list.length - TENANTS_FIRST)}
          </span>
        </button>
      )}
    </>
  );
}

export function Body({ q, d }: { q: Question; d: ItemDetail }) {
  const b = q.body;
  const pc = useIsPc();
  const P = t.panel;
  if (q.key === "buy") {
    const st = d.stations?.[0];
    const area = b.area_m2
      ? `${b.area_m2.toFixed(1)}㎡ (${Math.round(b.area_m2 / 3.3058)}평)`
      : null;
    // 감정평가서 한 줄(11/22 디자인 · 11/23): 요항 「서류와 다른 점」 원문 — 11가지 경우 T10 「확인 필요」를 만든 그 글
    const diff = d.appraisal?.points.find((p) => p.label === "서류와 다른 점");
    return (
      <>
        {diff && (
          <div className="appr-line">
            <div className="fs-sm fw-7">{t.apprLine}</div>
            <p className="m-0 mt-4">{diff.text}</p>
            <div className="fs-xs mt-4">{t.apprLineSrc(d.appraisal?.firm ?? null)}</div>
          </div>
        )}
        <Row label="주소" value={b.address ?? "-"} />
        {/* PC(11/22 디자인): 지도 | 입지 한 줄 · 정비구역 안 — 아래로 「가까운 역」 · 「건물과 땅」 칸 */}
        <div className="buy-top">
          <div className="minw-0">
            <ItemMap lat={d.lat} lon={d.lon} address={b.address ?? d.address} />
            <GoLinks keys={["roadview"]} d={d} />
          </div>
          {pc && (d.location?.line || d.location?.inside) && (
            <div className="buy-loc">
              <Stations d={d} part="head" />
            </div>
          )}
        </div>
        {pc ? (
          st && (
            <Panel
              id="station"
              title={P.station}
              sum={P.stationSum(
                d.location?.grade ?? null,
                st.name,
                st.walk_min,
                (d.stations?.length ?? 1) - 1,
              )}
              tag={d.location?.grade ? <span className="chip blue">{d.location.grade}</span> : null}
            >
              <Stations d={d} part="list" />
            </Panel>
          )
        ) : (
          <Stations d={d} />
        )}
        <Panel
          id="building"
          title={P.building}
          sum={[area?.replace(" ", ""), b.building?.built].filter(Boolean).join(" · ")}
        >
          {b.area_m2 && (
            <Row
              label="면적"
              value={`${b.area_m2.toFixed(1)}㎡ (${Math.round(b.area_m2 / 3.3058)}평)`}
            />
          )}
          {b.is_share && <Row label="" value={<b className="c-red">{t.share}</b>} />}
          {b.building && <BuildingRows g={b.building} />}
          {/* 구역 이름 · 단계를 못 이은 물건(「정비구역 안」만 앎)은 빈 줄이 되어 안 냄 — 위 띠에 이미 나옴(11/16) */}
          {b.redev && (b.redev.name || b.redev.stage || b.redev.biz_type) && (
            <Row
              label={t.redev}
              value={
                <>
                  {[b.redev.name, b.redev.biz_type, b.redev.stage].filter(Boolean).join(" · ")}
                  {pc && <GoLinks inline keys={["redev"]} d={d} />}
                </>
              }
              note={
                [
                  b.redev.homes && t.redevHomes(b.redev.homes),
                  b.redev.dates && t.redevDates(b.redev.dates, b.redev.dates_as_of),
                ]
                  .filter(Boolean)
                  .join(" / ") || null
              }
            />
          )}
          {b.redev && !pc && <GoLinks keys={["redev"]} d={d} />}
          {b.land_plan?.zones?.length > 0 && (
            <Row
              label={t.zoning}
              value={
                <>
                  {b.land_plan.zones.join(" · ")}
                  {pc && <GoLinks inline keys={["eum"]} d={d} />}
                </>
              }
              note={t.planFacilities(b.land_plan.facilities)}
            />
          )}
          {(!pc || !b.land_plan?.zones?.length) && <GoLinks keys={["eum"]} d={d} />}
          {b.area_stats?.items?.length > 0 && (
            <Row
              label={t.areaAvg}
              value={t.areaAvgValue(b.area_stats.items)}
              note={t.areaAvgNote(b.area_stats.items)}
            />
          )}
          {b.stores && (
            <Row label={t.stores} value={t.storesValue(b.stores)} note={t.storesNote(b.stores)} />
          )}
          <GoLinks keys={["sbiz"]} d={d} />
          {b.land_trades && (
            <Row
              label={t.landTrades}
              value={t.landTradesValue(b.land_trades)}
              note={t.landTradesNote(b.land_trades)}
            />
          )}
        </Panel>
        {b.note && (
          <p className="sub" style={{ whiteSpace: "pre-wrap" }}>
            {b.note}
          </p>
        )}
        {d.appraisal ? (
          <AppraisalPoints a={d.appraisal} court={d.court} caseNo={d.case_no} itemId={d.item_id} />
        ) : (
          <OriginalLink court={d.court} caseNo={d.case_no} itemId={d.item_id} earn />
        )}
      </>
    );
  }
  if (q.key === "hold") {
    const sigs = b.signals.filter((s: { status: string }) => s.status !== "모름");
    const signalBox = sigs.length > 0 && (
      <div className="hold-sigs">
        {sigs.map((s: { rule_id: string; title: string; level: string }) => (
          <div key={s.rule_id} className={s.level === "fatal" ? "sig fatal-t" : "sig"}>
            ◆ {s.title}
          </div>
        ))}
      </div>
    );
    const t0 = b.tenants[0] as Record<string, string | number | null> | undefined;
    const tenantSum = t0
      ? [
          `${t0.name ?? "임차인"} ${t0.part ?? ""}`.trim(),
          t0.move_in && `${t.moveIn} ${t0.move_in}`,
          t0.claim && `${t.claim} ${t0.claim}`,
        ]
          .filter(Boolean)
          .join(" · ") + (b.tenants.length > 1 ? ` ${P.more(b.tenants.length - 1)}` : "")
      : b.status_report
        ? t.tenantsNoneSeen
        : t.tenantsNone;
    const ft = d.failure_table ?? [];
    const fc: Record<string, number> = {};
    ft.forEach((r) => (fc[r.state] = (fc[r.state] ?? 0) + 1));
    const hit = fc["걸림"] ?? 0;
    return (
      <>
        {/* 위험 신호를 맨 위 한 판에(PC 11/22 · 휴대폰 11/23 디자인) */}
        {signalBox}
        <Panel id="tenant" title={P.tenant} sum={tenantSum}>
          {b.tenants.length === 0 && (
            <p className="sub">{b.status_report ? t.tenantsNoneSeen : t.tenantsNone}</p>
          )}
          <Tenants list={b.tenants} />
          <HoldDocLink />
        </Panel>
        {d.failure_table ? (
          <FailMobile rows={d.failure_table} />
        ) : (
          d.failure_types.length > 0 && (
            <div className="sub mt-8">
              {t.failureTypes}: {d.failure_types.map((x) => x.title).join(" · ")}
            </div>
          )
        )}
        {d.failure_table && pc && (
          <Panel
            id="fail"
            title={P.fail(ft.length)}
            sum={t.failFold(fc)}
            tag={hit > 0 ? <span className="chip red">{P.hit(hit)}</span> : null}
          >
            {/* 상태는 꼬리표 색(11/22 디자인): 걸림 빨강 · 확인함 초록 · 대비됨 파랑 · 해당 없음 회색 */}
            <table className="fail-table">
              <tbody>
                {d.failure_table.map((r) => (
                  <tr key={r.code}>
                    <td className="ft-code">{r.code}</td>
                    <td className="ft-title">{r.title}</td>
                    <td>
                      <span className={`chip ${FAIL_CHIP[r.state] ?? "gray"}`}>{r.state}</span>
                    </td>
                    <td className="sub">{r.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="sub mt-4">{t.failureTableNote}</div>
          </Panel>
        )}
        {!d.outcome?.closed && (
          <>
            <RegistryBox />
            <GoLinks keys={["iros"]} d={d} />
          </>
        )}
      </>
    );
  }
  // 실거래 · 매물 바로 가기 — PC 는 맨 위 한 줄(11/22 디자인), 휴대폰은 예전 자리
  const worthLinks = q.key === "worth" && (
    <div className="worth-links">
      {/* 지난 실거래 요약이 있는 단지(11/21)는 국토부 사이트 대신 옥스 안 「실거래 전체 보기」 */}
      <GoLinks
        keys={
          b.history_n > 0 ? ["naver", "valuemap", "disco"] : ["rt", "naver", "valuemap", "disco"]
        }
        d={d}
        lead={
          (b.history_n > 0 || b.nearby_ok) && (
            <Link className="link fs-sm" href={`/item/${encodeURIComponent(d.item_id)}/trades`}>
              {b.history_n > 0 ? copy.itemTrades.link : copy.itemTrades.nearLink}
            </Link>
          )
        }
      />
    </div>
  );
  if (q.key === "worth")
    return (
      <>
        {/* 실거래 · 시세 링크를 맨 위 한 줄로(PC 11/22 · 휴대폰 11/23) */}
        {worthLinks}
        {d.court_bidders?.avg != null && (
          <Row
            label={copy.me.courtBidders}
            value={copy.me.courtBiddersValue(d.court_bidders.avg, d.court_bidders.n)}
          />
        )}
        {b.range_krw && (
          <>
            <Row
              label={t.rangeLabel}
              value={
                <b>
                  {won(b.range_krw[0]) === won(b.range_krw[1])
                    ? won(b.range_krw[0])
                    : `${won(b.range_krw[0])} ~ ${won(b.range_krw[1])}`}
                </b>
              }
            />
            {b.assume_risk && (
              <p className="fs-sm c-amber mb-0">
                {copy.item.calc.assumeTitle} · {copy.item.calc.assumeNeed}
              </p>
            )}
            <p className="sub">{t.sample(b.rate.n)}</p>
            {b.market && (
              <>
                <Row label={t.market(b.market.n)} value={<b>{won(b.market.price_krw)}</b>} />
                <div className="sub m-0 fs-xs">
                  {t.recentTrades}{" "}
                  {b.market.recent
                    .slice(0, 3)
                    .map(
                      (x: { date: string; floor: number | null; price_krw: number }) =>
                        `${x.date.slice(2, 7).replace("-", ".")} ${x.floor ?? "-"}층 ${won(x.price_krw)}`,
                    )
                    .join(" · ")}
                </div>
              </>
            )}
            {b.near_market && (
              <>
                <Row
                  label={t.near.label(b.near_market.n, b.near_market.lots)}
                  value={
                    <b>
                      {won(b.near_market.p25_krw)} ~ {won(b.near_market.p75_krw)}
                    </b>
                  }
                />
                <div className="sub m-0 fs-xs">
                  {t.near.mid(won(b.near_market.p50_krw))} · {t.near.basis}
                </div>
              </>
            )}
            {b.land_value && (
              <>
                <Row
                  label={t.land.label}
                  value={
                    <b>
                      {won(b.land_value.low_krw)} ~ {won(b.land_value.high_krw)}
                    </b>
                  }
                />
                <div className="sub m-0 fs-xs">
                  {t.land.mid(won(b.land_value.mid_krw))} ·{" "}
                  {t.land.basis(
                    b.land_value.n,
                    b.land_value.land_m2,
                    won(b.land_value.land_unit.p50),
                    won(b.land_value.building_krw),
                  )}
                </div>
                {b.land_value.court_unit && (
                  <div className="sub m-0 fs-xs">
                    {t.land.court(won(b.land_value.court_unit), b.land_value.court_n)}
                  </div>
                )}
                <div className="sub m-0 fs-xs">{t.land.note}</div>
              </>
            )}
            {b.notes.map((n: string) => (
              <div key={n} className="fs-md c-amber py-2 px-0">
                ◆ {n}
              </div>
            ))}
          </>
        )}
        {b.complex && <ComplexBlock cx={b.complex} />}
        <GoLinks keys={["kb", "kapt"]} d={d} />
      </>
    );
  if (q.key === "cost")
    return (
      <>
        {pc ? (
          <>
            {/* PC(11/22 디자인): 놓치면 안 되는 날 세 칸 + 아래 한 줄(보증금은 머리 줄에 이미 있음) */}
            <div className="cost-days">
              {b.deadlines.map((x: { key: string; label: string; short: string }) => (
                <div key={x.key}>
                  <div className="sub m-0">{x.label}</div>
                  <b>{x.short}</b>
                </div>
              ))}
            </div>
            <p className="sub mt-10 mb-0">
              {b.schedule_line} · {t.deadlines}
            </p>
          </>
        ) : (
          <>
            <Row label={t.deposit} value={<b>{won(b.deposit_krw)}</b>} />
            <p className="fs-md mt-8 mb-4 mx-0">{b.schedule_line}</p>
            <div className="sub mt-8 mb-2 mx-0">{t.deadlines}</div>
            {b.deadlines.map((x: { key: string; label: string; short: string }) => (
              <Row key={x.key} label={x.label} value={x.short} />
            ))}
          </>
        )}
        {!d.outcome?.closed && (
          <div id="calc" className="cost-calc">
            <CalcBox id={d.item_id} />
          </div>
        )}
        <GoLinks keys={["price"]} d={d} />
      </>
    );
  return <CheckBody b={b} />;
}
