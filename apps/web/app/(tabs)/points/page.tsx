"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { DDay } from "@/components/dday";
import { OriginalLink } from "@/components/item/appraisal";
import { PageHeader } from "@/components/layout/page-header";
import { NeedLogin } from "@/components/need-login";
import { Delayed, SkRows } from "@/components/skeleton";
import {
  meApi,
  uploadAppraisal,
  uploadRegistry,
  type DocKind,
  type PointRow,
  type PointSummary,
} from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { parseTime } from "@/lib/format";

const t = copy.points;
const IROS = "https://www.iros.go.kr";
const KINDS: DocKind[] = ["registry", "appraisal"];

const dDay = (iso: string | null) =>
  iso ? Math.round((parseTime(iso).getTime() - new Date().setHours(0, 0, 0, 0)) / 864e5) : null;

function resultText(why: string, pts: number): string {
  const r = t.result[why];
  if (typeof r === "function") return r(t.pt(pts));
  return r ?? why;
}

// 포인트 벌기(11/12 대표님): 서류가 빈 물건 → 맡기기(10분) → 받는 곳 → 올리기 → 맞으면 포인트
export default function PointsPage() {
  const { session, ready } = useSession();
  const token = session?.access_token ?? "";
  const [sum, setSum] = useState<PointSummary | null>(null);
  const [rows, setRows] = useState<PointRow[] | null>(null);
  const [open, setOpen] = useState<{
    id: string;
    kind: DocKind;
    until: string;
    extended: boolean;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [, tick] = useState(0);
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    if (!token) return;
    meApi
      .points(token)
      .then(setSum)
      .catch(() => setSum(null));
    meApi
      .pointsBoard(token)
      .then(setRows)
      .catch(() => setRows([]));
  }, [token]);
  useEffect(load, [load]);

  // 맡긴 동안만 1초마다 남은 시간을 다시 그림
  useEffect(() => {
    if (!open) return;
    const h = setInterval(() => {
      if (parseTime(open.until).getTime() <= Date.now()) setOpen(null);
      tick((n) => n + 1);
    }, 1000);
    return () => clearInterval(h);
  }, [open]);

  if (!ready)
    return (
      <main className="page">
        <SkRows n={6} />
      </main>
    );
  if (!session) return <NeedLogin title={t.title} />;

  const take = (r: PointRow, kind: DocKind, extend = false) =>
    meApi
      .hold(token, r.item_id, kind, extend)
      .then(
        (h) => h.until && setOpen({ id: r.item_id, kind, until: h.until, extended: h.extended }),
      )
      .catch(() => {
        setNotice(t.taken);
        load();
      });

  const send = (r: PointRow, kind: DocKind, f: File | undefined) => {
    if (!f) return;
    setBusy(true);
    const done = (text: string) => {
      setNotice(`${r.place} ${t.kind[kind]} · ${text}`);
      setOpen(null);
      load();
    };
    (kind === "registry"
      ? uploadRegistry(token, r.item_id, f).then(() => done(t.registrySent))
      : uploadAppraisal(token, r.item_id, f).then((x) => done(resultText(x.why, x.points)))
    )
      .catch((e: Error) => setNotice(e.message))
      .finally(() => setBusy(false));
  };

  const leftSec = open
    ? Math.max(0, Math.round((parseTime(open.until).getTime() - Date.now()) / 1000))
    : 0;

  return (
    <main className="page">
      <PageHeader title={t.title} />
      <section className="pt-hero">
        <svg className="pt-coin" viewBox="0 0 48 48" aria-hidden="true">
          <circle cx="24" cy="24" r="20" />
          <path d="M19 15h7a5 5 0 0 1 0 10h-7M19 15v18" />
        </svg>
        <h2 className="pt-hero-title">{t.heroTitle}</h2>
        <p className="pt-hero-body">{t.heroBody}</p>
        <div className="pt-perks">
          {t.heroPerks.map(([k, v]) => (
            <div key={k}>
              <span>{k}</span>
              <b>{v}</b>
            </div>
          ))}
        </div>
        <p className="pt-hero-pay">{t.heroPay}</p>
        <ol className="pt-steps">
          {t.steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
      </section>

      <section className="section">
        <div className="sub m-0">{t.balance}</div>
        <div className="item-price">{sum ? t.pt(sum.balance) : "-"}</div>
        {notice && <div className="bg-panel r-14 p-12 mt-10 fs-md">{notice}</div>}
        {sum && (
          <p className="sub mt-4 mb-0">
            {t.today(
              sum.today.registry,
              sum.max.registry ?? 0,
              sum.today.appraisal,
              sum.max.appraisal ?? 0,
            )}
          </p>
        )}
      </section>

      <section className="section">
        <h2>{t.listTitle}</h2>
        <p className="sub mt-4">{t.listSub}</p>
        {!rows && (
          <Delayed>
            <SkRows n={6} />
          </Delayed>
        )}
        {rows?.length === 0 && <p className="sub mt-12">{t.empty}</p>}
        {rows?.map((r) => (
          <div key={r.item_id} className="mt-14">
            <Link href={`/item/${encodeURIComponent(r.item_id)}`} className="link fw-6">
              {r.place} {r.building ?? ""}
            </Link>
            <div className="sub mt-2">
              <DDay d={dDay(r.sale_date)} /> · {r.court} {r.case_no}
            </div>
            <div className="d-flex gap-8 f-wrap mt-8">
              {KINDS.filter((k) => r.need[k]).map((k) => (
                <button
                  key={k}
                  className={`btn sm ${open?.id === r.item_id && open.kind === k ? "primary" : "soft"}`}
                  onClick={() => take(r, k)}
                >
                  {t.kind[k]} {t.pt(sum?.points[k] ?? 0)}
                </button>
              ))}
            </div>
            {open?.id === r.item_id && (
              <div className="bg-panel r-14 p-12 mt-8">
                <div className="fs-sm fw-6">{t.left(Math.floor(leftSec / 60), leftSec % 60)}</div>
                {open.kind === "registry" ? (
                  <>
                    {/* 인터넷등기소는 열람 화면으로 바로 가는 주소가 없음(첫 화면 검색칸이 열람 입구) → 주소를 복사해 감 */}
                    <a
                      className="btn soft mt-10"
                      href={IROS}
                      target="_blank"
                      rel="noreferrer"
                      onClick={() => r.address && void navigator.clipboard?.writeText(r.address)}
                    >
                      {t.getRegistry}
                    </a>
                    <p className="sub fs-sm mt-6">{t.registryHint}</p>
                  </>
                ) : (
                  <OriginalLink court={r.court} caseNo={r.case_no} />
                )}
                <div className="btn-pair mt-10">
                  <button
                    className="btn primary"
                    disabled={busy}
                    onClick={() => file.current?.click()}
                  >
                    {busy ? t.sending : t.upload}
                  </button>
                  {!open.extended && leftSec < 180 && (
                    <button className="btn secondary" onClick={() => take(r, open.kind, true)}>
                      {t.more}
                    </button>
                  )}
                </div>
                <input
                  ref={file}
                  type="file"
                  accept="application/pdf"
                  hidden
                  onChange={(e) => {
                    send(r, open.kind, e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
              </div>
            )}
          </div>
        ))}
      </section>
    </main>
  );
}
