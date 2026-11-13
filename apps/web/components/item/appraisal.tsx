"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { AppraisalParts, ItemDetail } from "@/lib/api/items";
import { meApi, uploadAppraisal, type MyAppraisal } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { Row } from "@/components/calc-box";
import { won } from "@/lib/format";
import { t } from "@/components/item/shared";
import { copy } from "@/lib/copy.ko";

// 법원 경매사건검색 화면 — 감정평가서 원본은 손님이 법원에서 직접 열어 봄(11/7).
// pgjId 까지 붙여야 휴대폰에서도 첫 화면이 아니라 사건검색으로 바로 감(11/12 대표님)
const COURT_CASE_PAGE =
  "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml&pgjId=159M00";

// 감정평가 요점(11/4 평가사 쪽 사용 허락 · 11/12 가리지 않음, 평가사 이름을 곁에 붙임). 처음엔 세 칸만, 누르면 전부
export function AppraisalPoints({
  a,
  court,
  caseNo,
  itemId,
}: {
  a: NonNullable<ItemDetail["appraisal"]>;
  court: string;
  caseNo: string;
  itemId?: string;
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
      <OriginalLink pdf={a.pdf_url} court={court} caseNo={caseNo} itemId={itemId} earn />
    </div>
  );
}

// 물건 상세에서 바로 올리기(11/14 대표님): 법원에서 받은 파일을 이 자리에서 올리고, 어떻게 됐는지 이 자리에 남김
// (전에는 포인트 화면으로 가야 했고, 올린 뒤 결과가 한 번 뜨고 사라져 올렸는지 알 수 없었음)
function AppraisalUpload({ itemId }: { itemId: string }) {
  const p = copy.points;
  const { session } = useSession();
  const token = session?.access_token;
  const file = useRef<HTMLInputElement>(null);
  const [mine, setMine] = useState<MyAppraisal>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let stop = false;
    meApi
      .myAppraisal(token, itemId)
      .then((x) => !stop && setMine(x))
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, [token, itemId]);

  if (!token)
    return (
      <Link href="/points" className="link fs-sm mt-6 d-inline-block">
        {p.earn}
      </Link>
    );
  const why = (w: string, pts: number) => {
    const r = p.result[w];
    return typeof r === "function" ? r(p.pt(pts)) : (r ?? w);
  };
  const send = (f: File | undefined) => {
    if (!f) return;
    setBusy(true);
    setErr(null);
    uploadAppraisal(token, itemId, f)
      .then((x) => {
        if (x.why === "review") setMine({ status: "review" });
        else if (x.points || x.why === "first") setMine({ status: "ok", points: x.points });
        else setErr(why(x.why, x.points));
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  if (mine.status === "review") return <p className="chip orange mt-10">{p.herePending}</p>;
  if (mine.status === "ok")
    return (
      <p className="chip green mt-10">
        {mine.points ? p.hereDone(p.pt(mine.points)) : p.hereDoneNoPoint}
      </p>
    );
  return (
    <>
      <button className="btn primary mt-10" disabled={busy} onClick={() => file.current?.click()}>
        {busy ? p.sending : p.hereUpload}
      </button>
      <input
        ref={file}
        type="file"
        accept="application/pdf"
        hidden
        onChange={(e) => {
          send(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {(err || mine.status === "rejected") && (
        <p className="sub fs-sm mt-6 c-red">{err ?? why(mine.why ?? "mismatch", 0)}</p>
      )}
    </>
  );
}

// 감정평가서 원본(11/11 대표님): 받아 둔 원본이 있으면 바로 열고, 없으면 사건번호를 복사해 법원 사건검색 화면으로
// (법원 사이트에는 물건별 감정평가서 창으로 바로 가는 주소가 없음)
export function OriginalLink({
  pdf,
  court,
  caseNo,
  compact = false,
  earn = false,
  itemId,
}: {
  pdf?: string | null;
  court: string;
  caseNo: string;
  itemId?: string; // 있으면 이 자리에서 바로 올림(물건 상세, 11/14)
  compact?: boolean; // 머리 서류 줄에 놓는 작은 단추(11/11) — 안내 글 없이
  earn?: boolean; // 원본이 없을 때 「올리면 500P」(포인트 벌기로, 11/12)
}) {
  const [copied, setCopied] = useState(false);
  const c = t.appraisal;
  // 「2024타경12345」 → 연도 2024 · 번호 12345 (법원 화면은 법원·연도를 따로 고름)
  const [year = "", num = caseNo] = caseNo.split("타경");
  const cls = compact ? "btn soft sm" : "btn soft mt-10";
  if (pdf)
    return (
      <a className={cls} href={pdf} target="_blank" rel="noreferrer">
        {compact ? c.short : c.original}
      </a>
    );
  return (
    <>
      <a
        className={cls}
        href={COURT_CASE_PAGE}
        target="_blank"
        rel="noreferrer"
        onClick={() => {
          navigator.clipboard?.writeText(num).then(
            () => setCopied(true),
            () => setCopied(false),
          );
        }}
      >
        {compact ? c.short : c.court}
      </a>
      {(!compact || copied) && (
        <p className={`sub fs-sm ${compact ? "w-full m-0" : "mt-6"}`}>
          {copied ? c.copied(court, year, num) : c.courtHint(court, year, num)}
        </p>
      )}
      {earn &&
        (itemId ? (
          <AppraisalUpload itemId={itemId} />
        ) : (
          <Link href="/points" className="link fs-sm mt-6 d-inline-block">
            {copy.points.earn}
          </Link>
        ))}
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
