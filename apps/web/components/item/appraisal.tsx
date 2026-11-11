"use client";

import { useState } from "react";
import type { AppraisalParts, ItemDetail } from "@/lib/api/items";
import { Row } from "@/components/calc-box";
import { won } from "@/lib/format";
import { t } from "@/components/item/shared";

// 법원 사건 검색 화면 — 감정평가서 원본은 손님이 법원에서 직접 열어 봄(11/7)
const COURT_CASE_PAGE =
  "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml";

// 감정평가 요점(11/4 대표님 — 개인정보 가리고 사용 허락, 평가사 이름을 곁에 붙임). 처음엔 세 칸만, 누르면 전부
export function AppraisalPoints({
  a,
  court,
  caseNo,
}: {
  a: NonNullable<ItemDetail["appraisal"]>;
  court: string;
  caseNo: string;
}) {
  const [open, setOpen] = useState(false);
  const c = t.appraisal;
  const rows = open ? a.points : a.points.slice(0, 3);
  return (
    <div className="m-block mt-10">
      <div className="fs-md fw-7">
        {c.head}
        <span className="sub fw-4">
          {" "}
          · {a.firm ?? c.source}
          {a.price_date && ` · ${c.asOf(a.price_date)}`}
        </span>
      </div>
      {a.parts && <Parts p={a.parts} />}
      {rows.map((p) => (
        <div key={p.label} className="py-6 px-0 fs-sm">
          <b>{p.label}</b>
          <span className="sub d-block m-0">{p.text}</span>
        </div>
      ))}
      {a.points.length > 3 && (
        <button
          className="cond-row fold bg-bg mt-6"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <span className="fs-md">{open ? c.less : c.more(a.points.length - 3)}</span>
        </button>
      )}
      <OriginalLink pdf={a.pdf_url} court={court} caseNo={caseNo} />
    </div>
  );
}

// 감정평가서 원본(11/11 대표님): 받아 둔 원본이 있으면 바로 열고, 없으면 사건번호를 복사해 법원 사건검색 화면으로
// (법원 사이트에는 물건별 감정평가서 창으로 바로 가는 주소가 없음)
export function OriginalLink({
  pdf,
  court,
  caseNo,
}: {
  pdf?: string | null;
  court: string;
  caseNo: string;
}) {
  const [copied, setCopied] = useState(false);
  const c = t.appraisal;
  if (pdf)
    return (
      <a className="btn soft mt-10" href={pdf} target="_blank" rel="noreferrer">
        {c.original}
      </a>
    );
  return (
    <>
      <a
        className="btn soft mt-10"
        href={COURT_CASE_PAGE}
        target="_blank"
        rel="noreferrer"
        onClick={() => {
          navigator.clipboard?.writeText(caseNo).then(
            () => setCopied(true),
            () => setCopied(false),
          );
        }}
      >
        {c.court}
      </a>
      <p className="sub fs-sm mt-6">{copied ? c.copied(caseNo) : c.courtHint(court, caseNo)}</p>
    </>
  );
}

// 만 원 아래(제시외 창고 몇천 원)는 「0만」이 되지 않게 그대로
const small = (n: number) => (n < 10_000 ? `${n.toLocaleString("ko-KR")}원` : won(n));

// 감정가 나눔(11/7): 토지·건물 금액 · 땅만/건물만 · 대지권 · 제시외 건물 — 걸린 것만
function Parts({ p }: { p: AppraisalParts }) {
  const c = t.appraisal;
  const ex = p.extras.filter((x) => x.krw || x.use);
  return (
    <div className="mt-6">
      {p.kind === "land_only" && <Row label="" value={<b className="c-red">{c.landOnly}</b>} />}
      {p.kind === "building_only" && (
        <Row label="" value={<b className="c-red">{c.buildingOnly}</b>} />
      )}
      {p.kind === "land_and_building" && (
        <>
          <Row label={c.land} value={won(p.land_krw)} />
          <Row
            label={c.building}
            value={
              <>
                {won(p.building_krw)}
                {p.building_pct !== null && (
                  <span className="sub d-block m-0">{c.buildingPct(p.building_pct)}</span>
                )}
              </>
            }
          />
        </>
      )}
      {p.land_right_m2 !== null && p.land_total_m2 !== null && (
        <Row
          label={c.landRight}
          value={c.landRightV(String(p.land_right_m2), String(p.land_total_m2))}
        />
      )}
      {ex.length > 0 && (
        <Row
          label={c.extras}
          value={
            <>
              {c.extrasV(ex.length, p.extras_krw ? small(p.extras_krw) : null)}
              <span className="sub d-block m-0">
                {ex
                  .slice(0, 3)
                  .map((x) => [x.use, x.area_m2 && `${x.area_m2}㎡`].filter(Boolean).join(" "))
                  .join(" · ")}
              </span>
            </>
          }
        />
      )}
    </div>
  );
}
