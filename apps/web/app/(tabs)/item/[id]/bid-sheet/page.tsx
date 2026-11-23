"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PrintHead } from "@/components/print-head";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchBidCheck, fetchBidDay, type BidCheck, type BidDay } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { BidDaySheet } from "@/components/bid-day-sheet";
import { useIsPc } from "@/lib/use-pc";
import { todayKst, won } from "@/lib/format";

const t = copy.bidSheet;
const PLACES = ["천억", "백억", "십억", "억", "천만", "백만", "십만", "만", "천", "백", "십", "일"];

// 금액을 입찰표 칸(천억~일)에 맞춰 한 글자씩. 앞자리 빈칸은 비워 둠.
function Digits({ v }: { v: number | null }) {
  const s = v ? String(v).padStart(12, " ").slice(-12) : " ".repeat(12);
  return (
    <table className="bid-digits">
      <thead>
        <tr>
          {PLACES.map((p) => (
            <th key={p}>{p}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          {s.split("").map((ch, i) => (
            <td key={i}>{ch.trim()}</td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}

function Sheet() {
  const pc = useIsPc();
  const id = decodeURIComponent(String(useParams().id));
  const sp = useSearchParams();
  const [bid, setBid] = useState<number | null>(Number(sp.get("bid")) || null);
  const [text, setText] = useState(
    sp.get("bid") ? String(Math.round(Number(sp.get("bid")) / 10_000)) : "",
  );
  const [day, setDay] = useState<BidDay | null>(null);
  const [chk, setChk] = useState<BidCheck | null>(null);
  const [sure, setSure] = useState(false);
  const [meOpen, setMeOpen] = useState(false);
  const [mine, setMine] = useState({ name: "", tel: "", rrn: "", addr: "" });
  // 인쇄가 끝나면 이 기기 화면에 적은 입찰자 정보를 지움(저장하지 않음)
  useEffect(() => {
    const clear = () => setMine({ name: "", tel: "", rrn: "", addr: "" });
    window.addEventListener("afterprint", clear);
    return () => window.removeEventListener("afterprint", clear);
  }, []);

  useEffect(() => {
    fetchBidDay(id)
      .then(setDay)
      .catch(() => setDay(null));
  }, [id]);
  // 글자 칠 때마다 부르지 않고 멈춘 뒤 한 번(10/27)
  useEffect(() => {
    setSure(false);
    if (!bid) return setChk(null);
    let stale = false;
    const h = setTimeout(() => {
      fetchBidCheck(id, bid)
        .then((r) => !stale && setChk(r))
        .catch(() => !stale && setChk(null));
    }, 300);
    return () => {
      stale = true;
      clearTimeout(h);
    };
  }, [id, bid]);

  const canPrint = chk && chk.level !== "block" && (chk.level === "ok" || sure);
  const dep = chk?.deposit_krw ?? day?.deposit_krw ?? null;
  // 실수 막기 검사(11/22 디자인): 통과 ✓ 초록 · 확인할 것 ! 주황, 위에 「N개 중 M개 통과」
  const checks: [boolean, string][] = [
    [Boolean(chk), t.checks.korean],
    [Boolean(chk) && (chk?.level === "ok" || sure), t.checks.double],
    [Boolean(chk), chk?.resale ? t.checks.deposit20 : t.checks.deposit10],
    [Boolean(day?.item_no), t.checks.itemNo(day?.item_no ?? null)],
    [true, t.checks.privacy],
  ];
  const passed = checks.filter(([ok]) => ok).length;
  const me = (v: string) => v || t.f.mine;
  const head = [
    day ? `${day.court} ${day.case_no}` : null,
    day?.sale_date ? t.dayLine(day.sale_date) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  // 입찰자 정보(11/22 디자인): 이 기기 화면에만 적고 서버로 보내지 않음 · 인쇄가 끝나면 지움.
  // PC 는 입력 칸 안, 휴대폰은 따로 한 칸(11/23 M-Bid)
  const bsMe = (
    <div className="bs-me">
      <b>{t.meTitle}</b>
      <p className="sub mt-4 mb-0">{t.meHint}</p>
      {!meOpen ? (
        <button className="btn soft sm mt-10" onClick={() => setMeOpen(true)}>
          {t.meOpen}
        </button>
      ) : (
        <div className="bs-me-in">
          {(
            [
              ["name", t.f.name],
              ["tel", t.f.tel],
              ["rrn", t.f.rrn],
              ["addr", t.f.addr],
            ] as const
          ).map(([k, label]) => (
            <label key={k} className="d-block mt-8">
              <span className="sub">{label}</span>
              <input
                className="f-input"
                autoComplete="off"
                value={mine[k]}
                onChange={(e) => setMine({ ...mine, [k]: e.target.value })}
              />
            </label>
          ))}
        </div>
      )}
    </div>
  );
  return (
    <main className="page wide">
      <div className="no-print">
        {pc && (
          <Link href={`/item/${encodeURIComponent(id)}`} className="back-link">
            ‹ {t.back}
          </Link>
        )}
        <PageHeader
          title={t.title}
          back={`/item/${encodeURIComponent(id)}`}
          sub={head || undefined}
        />
      </div>
      <div className="pc-grid g-40-60">
        <div className="no-print">
          <section className="section mt-0">
            <h2>{t.inputTitle}</h2>
            <div className="sub">{t.hint}</div>
            {day && (
              <div className="bs-fields">
                <div>
                  <span className="sub">{t.f.court}</span>
                  <b>{day.court_full}</b>
                </div>
                <div>
                  <span className="sub">{t.f.caseNo}</span>
                  <b>{day.case_no}</b>
                </div>
              </div>
            )}
            {day && <div className="sub mt-6">{t.f.itemNoLine(day.item_no)}</div>}
            <label className="d-block mt-10">
              <span className="sub">{t.amount}</span>
              <input
                inputMode="numeric"
                value={text}
                onChange={(e) => {
                  const v = e.target.value.replace(/[^0-9]/g, "");
                  setText(v);
                  setBid(v ? Number(v) * 10_000 : null);
                }}
                className="f-input big bs-amount"
              />
            </label>
            {chk && (
              <div className="mt-10">
                <div className={chk.level === "ok" ? "fs-md fw-7 c-green" : "fs-lg fw-7"}>
                  {chk.korean}
                  {chk.level === "ok" ? ` · ${t.koreanOk}` : ""}
                </div>
                {chk.level !== "ok" && (
                  <div
                    className="fs-md mt-4 fw-7"
                    style={{ color: chk.level === "block" ? "var(--red)" : "var(--orange)" }}
                  >
                    {chk.message}
                  </div>
                )}
                {chk.level === "stop" && (
                  <label className="big-confirm">
                    <input
                      type="checkbox"
                      checked={sure}
                      onChange={(e) => setSure(e.target.checked)}
                    />
                    {t.sure(won(bid))}
                  </label>
                )}
                <div className="sub mt-6">{t.deposit(won(chk.deposit_krw), chk.resale)}</div>
              </div>
            )}
            {pc && bsMe}
          </section>
          {!pc && <section className="section">{bsMe}</section>}
          <section className="section">
            <h2>{t.checkTitle}</h2>
            <div className="sub">{t.checkSum(checks.length, passed)}</div>
            {checks.map(([ok, label]) => (
              <div key={label} className="bs-check">
                <span className={ok ? "bs-ok" : "bs-warn"} aria-hidden="true">
                  {ok ? "✓" : "!"}
                </span>
                <span className={ok ? "" : "c-orange fw-7"}>{label}</span>
              </div>
            ))}
            {!pc && (
              <Link href={`/item/${encodeURIComponent(id)}/bid-day`} className="menu-row">
                <span>{copy.bidDay.title}</span>
                <span className="sub">›</span>
              </Link>
            )}
          </section>
        </div>

        <section className="section mt-0 bs-preview">
          <div className="d-flex jc-between ai-start gap-12 no-print">
            <div>
              <h2>{t.preview}</h2>
              <div className="sub">{t.previewSub}</div>
            </div>
            {pc && (
              <div className="d-flex gap-8">
                <button
                  className="btn secondary sm"
                  disabled={!canPrint}
                  onClick={() => window.print()}
                >
                  {t.savePdf}
                </button>
                <button
                  className="btn primary sm"
                  disabled={!canPrint}
                  onClick={() => window.print()}
                >
                  {t.printOnly}
                </button>
              </div>
            )}
          </div>
          <div className="bs-paper-wrap">
            <div className="print-area bs-paper">
              <PrintHead
                title={t.printBrand}
                sub={[day?.court_full, day?.case_no].filter(Boolean).join(" ")}
                date={todayKst()}
              />
              <h2 className="ta-center fs-xl">{t.formTitle}</h2>
              <table className="bid-form">
                <tbody>
                  <tr>
                    <th>{t.f.court}</th>
                    <td>
                      {day?.court_full} {day?.dept}
                    </td>
                    <th>{t.f.date}</th>
                    <td className="nowrap">{day?.sale_date}</td>
                  </tr>
                  <tr>
                    <th>{t.f.caseNo}</th>
                    <td className="nowrap">{day?.case_no}</td>
                    <th>{t.f.itemNo}</th>
                    <td>{day?.item_no}</td>
                  </tr>
                  <tr>
                    <th>{t.f.name}</th>
                    <td className={mine.name ? "" : "handwrite"}>{me(mine.name)}</td>
                    <th>{t.f.tel}</th>
                    <td className={mine.tel ? "" : "handwrite"}>{me(mine.tel)}</td>
                  </tr>
                  <tr>
                    <th>{t.f.rrn}</th>
                    <td colSpan={3} className={mine.rrn ? "" : "handwrite"}>
                      {mine.rrn || t.f.rrnHint}
                    </td>
                  </tr>
                  <tr>
                    <th>{t.f.addr}</th>
                    <td colSpan={3} className={mine.addr ? "" : "handwrite"}>
                      {me(mine.addr)}
                    </td>
                  </tr>
                  <tr>
                    <th>{t.f.agent}</th>
                    <td colSpan={3} className="handwrite">
                      {t.f.agentHint}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="sub mt-10">
                {t.f.price} {bid ? `· ${chk?.korean ?? ""}` : ""}
              </div>
              <Digits v={bid} />
              <div className="sub mt-10">{t.f.deposit}</div>
              <Digits v={dep} />
              <div className="fs-md mt-10">{t.f.method}</div>
              <div className="fs-md mt-16 ta-right">{t.f.sign}</div>
              <div className="sub mt-12">{t.f.note}</div>
            </div>
          </div>
          <div className="sub mt-10 no-print">{t.envelope}</div>
        </section>
      </div>
      {pc && (
        <section className="section no-print mt-20">
          <div className="sub m-0">{t.dayCard}</div>
          <BidDaySheet id={id} wide />
        </section>
      )}
      {/* 휴대폰: 인쇄 단추는 아래 탭 위에 붙음(11/23 M-Bid) */}
      {!pc && (
        <div className="cta-bar no-print">
          <button className="btn primary" disabled={!canPrint} onClick={() => window.print()}>
            {t.print}
          </button>
        </div>
      )}
    </main>
  );
}

export default function BidSheetPage() {
  return (
    <Suspense>
      <Sheet />
    </Suspense>
  );
}
