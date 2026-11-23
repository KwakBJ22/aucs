"use client";

import { Delayed, SkRows } from "@/components/skeleton";
import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { fetchCase, fetchCases, type CaseDetail, type CaseRow } from "@/lib/api/pro";
import { copy } from "@/lib/copy.ko";
import { dday, todayKst, won } from "@/lib/format";
import { PrintHead } from "@/components/print-head";
import { useIsPc } from "@/lib/use-pc";
import { copyText } from "@/lib/copy-text";

const t = copy.proCases;
const IMP_CHIP = { high: "red", mid: "gray", low: "gray" } as const;

const TAX = "세금 교부청구";
const dot = (iso: string | null) => (iso ? iso.replace(/-0?/g, ".") : "");

// 요약 다섯 줄(11/22 디자인) — 문건 분류(core.case_events.category)로 셈. 없으면 「문건에 없음」.
function Summary({ d }: { d: CaseDetail }) {
  const S = t.sum;
  const of = (cat: string) => d.events.filter((e) => e.category === cat);
  const last = (l: CaseDetail["events"]) =>
    l
      .map((e) => e.event_date)
      .filter(Boolean)
      .sort()
      .pop() ?? null;
  const rehab = of("회생·파산");
  const late = d.events.filter((e) => e.after_deadline);
  const tax = of(TAX);
  const cred = of("채권자 바뀜");
  const lien = of("유치권 신고").length;
  const share = of("공유자 우선매수").length;
  const rows: [string, string | null, string | null, boolean][] = [
    [S.rehab, rehab.length ? S.yes : null, dot(last(rehab)), true],
    [
      S.late,
      late.length ? S.n(late.length) : null,
      d.claim_deadline ? S.deadline(dot(d.claim_deadline)) : null,
      true,
    ],
    [S.tax, tax.length ? S.n(tax.length) : null, tax.length ? S.taxSub : null, false],
    [S.creditor, cred.length ? S.yes : null, dot(last(cred)), false],
    [S.hold, lien + share ? S.yes : null, S.holdSub(lien, share) || null, true],
  ];
  return (
    <div className="case-sum mt-12">
      {rows.map(([k, v, sub, warn]) => (
        <div key={k} className="line-row py-6 px-0">
          <span className="sub">{k}</span>
          <span className="ta-right">
            <b className={v && warn ? "c-orange" : v ? "" : "sub"}>{v ?? S.none}</b>
            {v && sub && <span className="sub d-block fs-xs">{sub}</span>}
          </span>
        </div>
      ))}
      <p className="sub fs-xs mt-4 mb-0">{S.note}</p>
    </div>
  );
}

// 사건 한 장(11/22 디자인): 머리(사건 · 이름 + 복사 · 보고서) → 숫자 네 칸 → 진행 판단 판 → 요약 다섯 줄
// → 문건 표(중요한 것만 · 모두, 「무슨 뜻인가」). 중요한 것만 볼 때 세금 교부청구는 한 줄로 묶음.
function Detail({ d, place }: { d: CaseDetail; place?: string | null }) {
  const [all, setAll] = useState(false);
  const [copied, setCopied] = useState(false);
  const picked = d.events.filter((e) => all || e.importance !== "low" || e.after_deadline);
  const taxes = picked.filter((e) => e.category === TAX);
  const ev =
    all || taxes.length < 2 ? picked : picked.filter((e) => e.category !== TAX || e === taxes[0]);
  const taxRange = taxes.length
    ? `${dot(taxes[0]!.event_date)} ~ ${dot(taxes[taxes.length - 1]!.event_date)}`
    : "";
  const it = d.items[0];
  return (
    <div>
      <PrintHead title={t.printBrand} sub={`${d.court} ${d.case_no}`} date={todayKst()} />
      <div className="d-flex jc-between ai-start gap-12 case-head">
        <div className="minw-0">
          <div className="sub">
            {d.court} {d.case_no}
            {d.dept ? ` · ${d.dept}` : ""}
            {it?.sale_date ? ` · ${t.saleDate(it.sale_date.slice(5).replace("-", "/"))}` : ""}
            {it ? ` · ${dday(it.d_day)}` : ""}
          </div>
          <h2 className="case-title">{place ?? d.case_no}</h2>
        </div>
        <div className="d-flex gap-8 no-print f-none">
          <button
            className="btn secondary sm"
            onClick={() => void copyText(d.case_no).then(() => setCopied(true))}
          >
            {copied ? copy.item.pc.copied : copy.item.pc.copy}
          </button>
          <button className="btn secondary sm" onClick={() => window.print()}>
            {t.report}
          </button>
        </div>
      </div>
      <div className="case-tiles">
        {(
          [
            [t.cards.progress, d.progress ?? t.cards.normal, Boolean(d.progress)],
            [t.cards.docs, `${d.events.length}건`, false],
            [t.cards.high, `${d.events.filter((e) => e.importance === "high").length}건`, false],
            [t.cards.late, `${d.events.filter((e) => e.after_deadline).length}건`, false],
          ] as [string, string, boolean][]
        ).map(([k, v, warn]) => (
          <div key={k}>
            <div className="sub m-0">{k}</div>
            <b className={warn ? "c-orange" : ""}>{v}</b>
          </div>
        ))}
      </div>
      {d.progress && (
        <div className="case-warn">
          ◆ {t.progress}: {d.progress}
        </div>
      )}
      {d.claim_deadline && <div className="sub mt-8">{t.deadline(d.claim_deadline)}</div>}
      <Summary d={d} />
      {d.items.map((i) => (
        <Link
          key={i.item_id}
          prefetch={false}
          href={`/item/${encodeURIComponent(i.item_id)}`}
          className="d-block fs-md py-6 px-0"
        >
          {i.item_no}. {i.usage_name} · {won(i.min_price_krw)}{" "}
          <span className="sub">
            {i.sale_date?.slice(5)} {dday(i.d_day)} ›
          </span>
        </Link>
      ))}
      <div className="d-flex f-wrap gap-4 my-10 mx-0">
        {d.counts.map(([c, n]) => (
          <span key={c} className="chip gray">
            {c} {n}
          </span>
        ))}
      </div>
      <div className="d-flex jc-between ai-center mt-16">
        <b className="case-flow">{t.flow}</b>
        <span className="scope-seg no-print" role="group">
          <button className={!all ? "on" : ""} onClick={() => setAll(false)}>
            {t.importantOnly}
          </button>
          <button className={all ? "on" : ""} onClick={() => setAll(true)}>
            {t.showAll(d.events.length)}
          </button>
        </span>
      </div>
      <div className="ox-auto mt-10">
        <table className="pro-table case-table">
          <thead>
            <tr>
              <th>{t.cols.date}</th>
              <th>{t.cols.cat}</th>
              <th>{t.cols.imp}</th>
              <th>{t.meanCol}</th>
              <th>{t.cols.text}</th>
            </tr>
          </thead>
          <tbody>
            {ev.map((e, i) => {
              const group = !all && e.category === TAX && taxes.length > 1;
              return (
                <tr key={i}>
                  <td className="nowrap">{group ? taxRange : e.event_date}</td>
                  <td>{group ? t.taxGroup(taxes.length) : e.category}</td>
                  <td>
                    <span className={`chip ${IMP_CHIP[e.importance]}`}>
                      {t.imp[e.importance]}
                      {e.after_deadline ? ` · ${t.lateTag}` : ""}
                    </span>
                  </td>
                  <td className="case-mean">
                    {e.after_deadline ? t.lateMeaning : (t.meaning[e.category] ?? "")}
                  </td>
                  <td className="case-text">
                    {group ? "" : `${e.kind ?? ""} ${e.text_masked ?? ""}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Cases() {
  const router = useRouter();
  const sp = useSearchParams();
  const cat = sp.get("category") ?? "";
  const id = sp.get("id") ?? "";
  const sq = sp.get("q") ?? "";
  const [list, setList] = useState<CaseRow[] | null>(null);
  const [cats, setCats] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [d, setD] = useState<CaseDetail | null>(null);
  const pc = useIsPc();
  // 휴대폰(11/18 대표님): 누르면 상세만 한 화면으로 — 목록이 길어 아래에 열린 상세가 안 보였음.
  // 열 때 보던 자리를 적어 두고, 「← 목록」 · 뒤로가기로 돌아오면 그 자리로.
  const listY = useRef<number | null>(null);
  const openedHere = useRef(false);
  const open = (caseId: string) => {
    if (pc) return go({ id: caseId });
    listY.current = window.scrollY;
    openedHere.current = true;
    const p = new URLSearchParams(sp.toString());
    p.set("id", caseId);
    router.push(`/pro/cases?${p}`); // 뒤로가기로 목록에 돌아오게 push
  };
  const close = () => {
    if (openedHere.current) router.back();
    else go({ id: "" }); // 주소로 바로 들어온 경우
  };
  useEffect(() => {
    if (pc) return;
    if (id) {
      window.scrollTo(0, 0);
      return;
    }
    openedHere.current = false;
    const y = listY.current;
    if (y == null) return;
    listY.current = null;
    requestAnimationFrame(() => window.scrollTo(0, y));
  }, [id, pc]);

  const go = (patch: Record<string, string>) => {
    const p = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    router.replace(`/pro/cases?${p}`);
  };
  // 사건을 고를 때(주소의 id만 바뀔 때)는 목록을 다시 부르지 않음(10/27)
  useEffect(() => {
    let stale = false;
    setList(null);
    fetchCases(cat || undefined, sq || undefined)
      .then((r) => {
        if (stale) return;
        setList(r.cases);
        setCats(r.categories);
      })
      .catch(() => !stale && setList([]));
    return () => {
      stale = true;
    };
  }, [cat, sq]);
  useEffect(() => {
    if (!id) return setD(null);
    fetchCase(id)
      .then(setD)
      .catch(() => setD(null));
  }, [id]);

  if (!pc && id)
    return (
      <main className="page pro-page">
        <PageHeader title={t.title} />
        <button type="button" className="link mb-8 no-print" onClick={close}>
          {t.backList}
        </button>
        <section className="section m-0 print-area">
          {d ? (
            <Detail d={d} />
          ) : (
            <Delayed>
              <SkRows n={8} />
            </Delayed>
          )}
        </section>
      </main>
    );

  return (
    <main className="page wide pro-page">
      <PageHeader title={t.title} />
      <div className="sub mb-8 no-print">{t.sub}</div>
      <div className="d-flex gap-6 f-wrap mb-8 no-print">
        <button
          className={`pill pick-pill${!cat ? " on" : ""}`}
          onClick={() => go({ category: "" })}
        >
          {!cat ? `✓ ${t.all}` : t.all}
        </button>
        {cats.map((c) => (
          <button
            key={c}
            className={`pill pick-pill${cat === c ? " on" : ""}`}
            onClick={() => go({ category: c })}
          >
            {cat === c ? `✓ ${c}` : c}
          </button>
        ))}
        <input
          placeholder={t.search}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go({ q })}
          className="case-search"
        />
      </div>
      <div className="pc-grid g-26-74">
        <section className="section m-0 no-print">
          {list === null && (
            <Delayed>
              <SkRows n={8} />
            </Delayed>
          )}
          {list?.length === 0 && <div className="sub">{t.empty}</div>}
          {list?.map((c) => (
            <button
              key={c.case_id}
              onClick={() => open(c.case_id)}
              className={`case-row${c.case_id === id ? " on" : ""}`}
            >
              <div className="sub">
                {c.court} {c.case_no} · {dday(c.d_day)}
              </div>
              <div className="case-row-t">{c.place}</div>
              <div className="case-row-f">
                {[...c.flags, ...(c.late > 0 ? [t.lateN(c.late)] : [])].join(" · ")}
              </div>
            </button>
          ))}
        </section>
        <section className="section m-0 print-area">
          {d ? (
            <Detail d={d} place={list?.find((c) => c.case_id === id)?.place} />
          ) : (
            <div className="sub">{t.pick}</div>
          )}
        </section>
      </div>
      <div className="sub mt-8 no-print">{t.note}</div>
    </main>
  );
}

export default function ProCasesPage() {
  return (
    <Suspense>
      <Cases />
    </Suspense>
  );
}
