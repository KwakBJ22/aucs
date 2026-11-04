"use client";

import { Logo } from "@/components/logo";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchRegions, type RegionRow } from "@/lib/api/items";
import { SIGUNGU } from "@/lib/regions";
import { Sk } from "@/components/skeleton";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { loadProfile, saveProfile, type Purpose } from "@/lib/profile";
import { track } from "@/lib/track";

const t = copy.start;
const wrap = {
  maxWidth: 480,
  margin: "0 auto",
  minHeight: "100dvh",
  display: "flex",
  flexDirection: "column" as const,
  padding: "40px 24px 24px",
  background: "var(--surface)",
};
const h1 = {
  margin: "0 0 8px",
  fontSize: 26,
  lineHeight: 1.35,
  fontWeight: 700,
  whiteSpace: "pre-line" as const,
};

function Progress({ step }: { step: number }) {
  return (
    <div className="d-flex gap-6 mb-24">
      {[1, 2, 3].map((n) => (
        <div
          key={n}
          className="f-1 r-4"
          style={{ height: 4, background: n <= step ? "var(--blue)" : "var(--line)" }}
        />
      ))}
    </div>
  );
}

export default function Start() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  // 이름은 바로(코드에 둔 목록), 숫자는 서버에서 받은 뒤 채움(11/4 — 첫 방문에 서버가 깨는 몇 초를 기다리지 않게)
  const [counts, setCounts] = useState<RegionRow[] | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [man, setMan] = useState(""); // 만 원 단위 입력
  const [purpose, setPurpose] = useState<Purpose>("live");

  // 「조건 바꾸기」로 다시 오면 지난 답을 미리 채움(11/1 — 예전엔 처음부터 다시 골라야 했음)
  useEffect(() => {
    const p = loadProfile();
    if (!p) return;
    setPicked(p.regions ?? []);
    if (p.cash) setMan(String(Math.round(p.cash / 10_000)));
    if (p.purpose) setPurpose(p.purpose);
  }, []);
  useEffect(() => {
    fetchRegions()
      .then(setCounts)
      .catch(() => setCounts([]));
  }, []);

  const regions = useMemo(() => {
    const got = new Map((counts ?? []).map((r) => [`${r.sido}-${r.sigungu}`, r.items]));
    const base = SIGUNGU.map(([sido, sigungu]) => ({
      sido,
      sigungu,
      items: got.get(`${sido}-${sigungu}`) ?? null,
    }));
    const known = new Set(base.map((r) => `${r.sido}-${r.sigungu}`));
    const extra = (counts ?? []).filter((r) => !known.has(`${r.sido}-${r.sigungu}`));
    return [...base, ...extra];
  }, [counts]);
  const shown = useMemo(() => regions.filter((r) => !q || r.sigungu.includes(q)), [regions, q]);
  const count = regions
    .filter((r) => picked.includes(r.sigungu))
    .reduce((a, r) => a + (r.items ?? 0), 0);
  const cash = man ? Number(man) * 10_000 : null;

  function finish() {
    saveProfile({ regions: picked, cash, purpose });
    track("start_done");
    router.replace("/home");
  }

  return (
    <main style={wrap}>
      {step === 1 && (
        <div className="mb-16">
          <Logo />
        </div>
      )}
      <Progress step={step} />
      {step > 1 && (
        <button
          onClick={() => setStep(step - 1)}
          className="b-0 bg-none ta-left c-muted fs-md p-0 mb-8 mh-44"
        >
          {t.back} {t.step(step)}
        </button>
      )}

      {step === 1 && (
        <>
          <h1 style={h1}>{t.regionTitle}</h1>
          <p className="sub fs-base mt-0 mb-16 mx-0">{t.regionHint}</p>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t.regionSearch}
            className="r-14 b-0 py-0 px-14 fs-base bg-panel c-text"
            style={{ height: 48 }}
          />
          <div
            className="d-flex f-wrap gap-8 mt-14 oy-auto f-1"
            style={{ alignContent: "flex-start" }}
          >
            {shown.map((r) => {
              const on = picked.includes(r.sigungu);
              return (
                <button
                  key={`${r.sido}-${r.sigungu}`}
                  onClick={() =>
                    setPicked(on ? picked.filter((x) => x !== r.sigungu) : [...picked, r.sigungu])
                  }
                  className="mh-40 py-0 px-12 r-20 b-0 fs-md"
                  style={{
                    background: on ? "var(--blue-soft)" : "var(--panel)",
                    color: on ? "var(--blue-text)" : "var(--text)",
                    fontWeight: on ? 700 : 400,
                  }}
                >
                  {r.sigungu}{" "}
                  {r.items == null ? (
                    counts ? null : (
                      <Sk className="sk-num" />
                    )
                  ) : (
                    <span className="c-muted fs-xs">{r.items}</span>
                  )}
                </button>
              );
            })}
          </div>
          {picked.length > 0 && counts && counts.length > 0 && (
            <div className="fs-sm c-green my-12 mx-0">{t.count(count)}</div>
          )}
          <button className="btn primary mt-16" disabled={!picked.length} onClick={() => setStep(2)}>
            {t.next}
          </button>
        </>
      )}

      {step === 2 && (
        <>
          <h1 style={h1}>{t.cashTitle}</h1>
          <p className="sub fs-base mt-0 mb-24 mx-0">{t.cashHint}</p>
          <div
            className="fw-7 pb-10 mh-56"
            style={{ fontSize: 34, borderBottom: "2px solid var(--blue)" }}
          >
            {cash ? won(cash) : ""}
            {!cash && <span className="c-faint fs-2xl">0{t.cashUnit}</span>}
          </div>
          <div className="d-flex gap-8 mt-16">
            {[1000, 5000, 10000].map((add) => (
              <button
                key={add}
                onClick={() => setMan(String((Number(man) || 0) + add))}
                className="f-1 r-14 b-0 bg-panel fs-md"
                style={{ height: 40 }}
              >
                +{won(add * 10_000)}
              </button>
            ))}
          </div>
          <div className="f-1" />
          <div
            className="d-grid gap-4 mb-12"
            style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}
          >
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "⌫"].map((k) => (
              <button
                key={k}
                aria-label={k === "⌫" ? "지우기" : k}
                onClick={() =>
                  setMan(k === "⌫" ? man.slice(0, -1) : (man + k).replace(/^0+/, "").slice(0, 7))
                }
                className="b-0 bg-none fs-2xl"
                style={{ height: 52 }}
              >
                {k}
              </button>
            ))}
          </div>
          <button className="btn primary" onClick={() => setStep(3)}>
            {t.next}
          </button>
          <button
            onClick={() => {
              setMan("");
              setStep(3);
            }}
            className="b-0 bg-none c-muted fs-md mt-12 mh-44"
          >
            {t.unsure}
          </button>
        </>
      )}

      {step === 3 && (
        <>
          <h1 style={h1}>{t.purposeTitle}</h1>
          <p className="sub fs-base mt-0 mb-24 mx-0">{t.purposeHint}</p>
          <div className="d-flex f-col gap-12">
            {(Object.keys(t.purposes) as Purpose[]).map((p) => (
              <button
                key={p}
                onClick={() => setPurpose(p)}
                className="d-flex f-col ai-start gap-4 p-20 r-16 ta-left b-0"
                style={{
                  background: purpose === p ? "var(--blue-soft)" : "var(--surface)",
                  color: purpose === p ? "var(--blue-text)" : "var(--text)",
                }}
              >
                <span className="fs-lg fw-7">{t.purposes[p][0]}</span>
                <span className="sub fs-md">{t.purposes[p][1]}</span>
              </button>
            ))}
          </div>
          <div className="f-1" />
          <button className="btn primary" onClick={finish}>
            {t.done}
          </button>
        </>
      )}
    </main>
  );
}
