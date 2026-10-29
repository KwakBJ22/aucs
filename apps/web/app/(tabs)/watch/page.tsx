"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ItemCard } from "@/components/item-card";
import { LoadError } from "@/components/load-error";
import { NeedLogin } from "@/components/need-login";
import { loadRecent, type Recent } from "@/lib/recent";
import { PageHeader } from "@/components/layout/page-header";
import { MOVABLE, WorkspacePanel } from "@/components/workspace-panel";
import { meApi, WATCH_STEPS, type WatchCard, type WatchStep } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { useIsPc } from "@/lib/use-pc";

const t = copy.watch;

// 휴대폰: 단계 칩 누르면 바꿀 단계가 펼쳐짐
function StepRow({
  c,
  onMove,
  onCompare,
}: {
  c: WatchCard;
  onMove: (s: WatchStep) => void;
  onCompare: () => void;
}) {
  const [open, setOpen] = useState(false);
  const choices = c.step === "result" ? (["after"] as WatchStep[]) : MOVABLE;
  return (
    <div className="pt-0 pb-12 pl-48 pr-0 d-flex gap-6 f-wrap">
      {!open ? (
        <>
          {c.changed && (
            <span className="chip orange mh-32" title={t.changedHint}>
              {t.changed}
            </span>
          )}
          <button className="chip green b-0 mh-32" onClick={() => setOpen(true)}>
            {t.steps[c.step]} ▾
          </button>
          <Link href={`/watch/${encodeURIComponent(c.item_id)}`} className="chip gray mh-32">
            {copy.ws.open} ›
          </Link>
          {c.step === "result" ? (
            <Link href="/me" className="chip gray mh-32">
              {t.resultShort} ›
            </Link>
          ) : (
            <button
              className={`${`chip ${c.in_compare ? "green" : "gray"}`} b-0 mh-32`}

              onClick={onCompare}
            >
              {c.in_compare ? copy.compare.added : copy.compare.add}
            </button>
          )}
        </>
      ) : (
        <>
          <div className="sub w-full m-0">{t.moveHint}</div>
          {choices.map((s) => (
            <button
              key={s}
              className={`${`chip ${s === c.step ? "green" : "gray"}`} b-0 mh-36`}

              onClick={() => {
                setOpen(false);
                if (s !== c.step) onMove(s);
              }}
            >
              {t.steps[s]}
            </button>
          ))}
        </>
      )}
    </div>
  );
}

// PC 보드의 작은 카드
function BoardCard({ c, on, onPick }: { c: WatchCard; on: boolean; onPick: () => void }) {
  return (
    <button className={`board-card${on ? " on" : ""}`} onClick={onPick}>
      <span className="sub m-0 fs-xs">
        <b style={{ color: c.d_day != null && c.d_day <= 7 ? "var(--red)" : "var(--amber)" }}>
          {dday(c.d_day)}
        </b>{" "}
        · {c.court}
        {c.changed && (
          <b className="c-amber" title={t.changedHint}>
            {" "}
            · {t.changed}
          </b>
        )}
      </span>
      <span className="clamp2 fs-sm fw-6 mt-2">
        {c.building?.split(" ")[0] ?? c.usage} <span className="sub">{c.place}</span>
      </span>
      <span className="fs-base fw-7 d-block mt-4">{won(c.min_price_krw)}</span>
      {c.in_compare && <span className="chip green mt-6">{copy.compare.added}</span>}
    </button>
  );
}

export default function Watch() {
  const { session, ready } = useSession();
  const pc = useIsPc();
  const [list, setList] = useState<WatchCard[] | null>(null);
  const [only, setOnly] = useState<WatchStep | null>(null);
  const [msg, setMsg] = useState("");
  const [pick, setPick] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);
  const [onlyChanged, setOnlyChanged] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tries, setTries] = useState(0);
  const [recent, setRecent] = useState<Recent[] | null>(null); // 「최근 본」을 펼쳤을 때만

  useEffect(() => {
    if (!session) return;
    setFailed(false);
    meApi
      .watch(session.access_token)
      .then((l) => {
        setList(l);
        setPick((p) => p ?? l[0]?.item_id ?? null);
      })
      .catch(() => setFailed(true));
  }, [session, tries]);

  if (!ready) return null;
  if (!session) return <NeedLogin title={copy.tabs.watch} />;
  const token = session.access_token;

  const move = (id: string, step: WatchStep) => {
    setList((l) => l?.map((x) => (x.item_id === id ? { ...x, step } : x)) ?? l);
    meApi.setStep(token, id, step).catch(() => {});
  };
  const toggleCompare = (c: WatchCard) => {
    const on = !c.in_compare;
    if (on && (list?.filter((x) => x.in_compare).length ?? 0) >= 5) {
      setMsg(copy.compare.full(5));
      return;
    }
    setMsg("");
    setList((l) => l?.map((x) => (x.item_id === c.item_id ? { ...x, in_compare: on } : x)) ?? l);
    (on ? meApi.addCompare : meApi.removeCompare)(token, c.item_id).catch(() => {});
  };
  const inCompare = list?.filter((x) => x.in_compare).length ?? 0;
  const count = (s: WatchStep) => list?.filter((x) => x.step === s).length ?? 0;
  const header = (
    <PageHeader
      title={t.title}
      sub={list ? t.summary(list.length, inCompare) : undefined}
      right={
        <div className="d-flex gap-6">
          <button
            className={`${`chip ${recent ? "green" : "gray"}`} b-0 mh-32`}

            onClick={() => setRecent(recent ? null : loadRecent())}
          >
            {t.recent}
          </button>
          <Link href="/compare" className="chip gray mh-32">
            {copy.compare.title} {inCompare} ›
          </Link>
        </div>
      }
    />
  );
  // 최근 본 물건(이 기기) — 관심에 안 담은 것도 다시 찾기 쉽게
  const recentBox = recent && (
    <section className="section">
      <h2>{t.recent}</h2>
      {recent.length === 0 && <p className="sub">{t.recentEmpty}</p>}
      {recent.map((r) => (
        <Link
          key={r.id}
          href={`/item/${encodeURIComponent(r.id)}`}
          className="d-block py-10 px-0 fs-md c-inherit"
        >
          {r.label} ›
        </Link>
      ))}
    </section>
  );
  const errorBox = failed && !list && <LoadError onRetry={() => setTries((n) => n + 1)} />;
  const empty = list && list.length === 0 && (
    <section className="section">
      <p className="sub">{t.empty}</p>
      <Link href="/find">{copy.find.title} ›</Link>
    </section>
  );

  // PC: 단계 7칸 보드(또는 표) + 오른쪽 40% 작업 공간 전부
  if (pc)
    return (
      <main className="page">
        {header}
        {recentBox}
        {errorBox}
        {msg && <div className="sub c-amber">{msg}</div>}
        {empty}
        {list && list.length > 0 && (
          <div className="pc-grid g-60-40">
            <section className="section mt-0">
              <div className="d-flex jc-between ai-center">
                <h2>{t.boardTitle}</h2>
                <button className="chip gray b-0 mh-32" onClick={() => setAsTable(!asTable)}>
                  {asTable ? t.asBoard : t.asTable}
                </button>
              </div>
              {asTable ? (
                <div className="ox-auto mt-8">
                  <table className="pro-table">
                    <thead>
                      <tr>
                        <th>{t.cols.step}</th>
                        <th>{t.cols.date}</th>
                        <th>{t.cols.place}</th>
                        <th>{t.cols.min}</th>
                        <th>{t.cols.compare}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.map((c) => (
                        <tr
                          key={c.item_id}
                          onClick={() => setPick(c.item_id)}
                          className={`${pick === c.item_id ? "row-on" : ""} cur-pointer`}
                        >
                          <td>{t.steps[c.step]}</td>
                          <td>
                            {dday(c.d_day)} {c.sale_date}
                          </td>
                          <td>
                            {c.court} {c.case_no} · {c.place} {c.building ?? c.usage}
                          </td>
                          <td>{won(c.min_price_krw)}</td>
                          <td>
                            <button
                              className={`${`chip ${c.in_compare ? "green" : "gray"}`} b-0`}

                              onClick={(e) => {
                                e.stopPropagation();
                                toggleCompare(c);
                              }}
                            >
                              {c.in_compare ? copy.compare.added : copy.compare.add}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="board">
                  {WATCH_STEPS.map((s) => (
                    <div key={s} className={`board-col${count(s) === 0 ? " empty" : ""}`}>
                      <div className="board-head">
                        {t.steps[s]} <span className="sub">{count(s)}</span>
                      </div>
                      {list
                        .filter((x) => x.step === s)
                        .map((c) => (
                          <BoardCard
                            key={c.item_id}
                            c={c}
                            on={pick === c.item_id}
                            onPick={() => setPick(c.item_id)}
                          />
                        ))}
                    </div>
                  ))}
                </div>
              )}
              <div className="sub mt-8">{t.boardHint}</div>
            </section>
            <div
              className="pc-sticky oy-auto quiet-scroll"
              style={{ maxHeight: "calc(100vh - 140px)" }}
            >
              {pick && (
                <WorkspacePanel
                  key={pick}
                  id={pick}
                  token={token}
                  all
                  onStep={(s) => move(pick, s)}
                />
              )}
            </div>
          </div>
        )}
      </main>
    );

  const nChanged = list?.filter((x) => x.changed).length ?? 0;
  const shownList = onlyChanged ? (list?.filter((x) => x.changed) ?? null) : list;
  const groups = WATCH_STEPS.filter((s) =>
    only ? s === only : (shownList?.some((x) => x.step === s) ?? false),
  );
  return (
    <main className="page">
      {header}
      {recentBox}
      {errorBox}
      {msg && <div className="sub c-amber mb-6">{msg}</div>}
      {list && list.length > 0 && (
        <div className="d-flex gap-6 ox-auto pb-4">
          <button
            className={`${`chip ${only === null ? "green" : "gray"}`} b-0 mh-32 nowrap`}

            onClick={() => {
              setOnly(null);
              setOnlyChanged(false);
            }}
          >
            {t.all} {list.length}
          </button>
          {nChanged > 0 && (
            <button
              className={`${`chip ${onlyChanged ? "green" : "orange"}`} b-0 mh-32 nowrap`}

              onClick={() => setOnlyChanged(!onlyChanged)}
              title={t.changedHint}
            >
              {t.changed} {nChanged}
            </button>
          )}
          {WATCH_STEPS.filter((s) => count(s) > 0).map((s) => (
            <button
              key={s}
              className={`${`chip ${only === s ? "green" : "gray"}`} b-0 mh-32 nowrap`}

              onClick={() => setOnly(only === s ? null : s)}
            >
              {t.steps[s]} {count(s)}
            </button>
          ))}
        </div>
      )}
      {empty}
      {shownList &&
        groups.map((s) => (
          <section key={s} className="section pt-12 pb-0">
            <h2>
              {t.steps[s]} <span className="sub">{count(s)}</span>
            </h2>
            {shownList
              .filter((x) => x.step === s)
              .map((c) => (
                <div key={c.item_id}>
                  <ItemCard c={c} />
                  <StepRow
                    c={c}
                    onMove={(st) => move(c.item_id, st)}
                    onCompare={() => toggleCompare(c)}
                  />
                </div>
              ))}
          </section>
        ))}
    </main>
  );
}
