"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchRegions, type RegionRow } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";
import { saveProfile, type Purpose } from "@/lib/profile";

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
    <div style={{ display: "flex", gap: 6, marginBottom: 24 }}>
      {[1, 2, 3].map((n) => (
        <div
          key={n}
          style={{
            flexGrow: 1,
            height: 4,
            borderRadius: 2,
            background: n <= step ? "var(--blue)" : "var(--line)",
          }}
        />
      ))}
    </div>
  );
}

export default function Start() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [man, setMan] = useState(""); // 만 원 단위 입력
  const [purpose, setPurpose] = useState<Purpose>("live");

  useEffect(() => {
    fetchRegions()
      .then(setRegions)
      .catch(() => setRegions([]));
  }, []);

  const shown = useMemo(() => regions.filter((r) => !q || r.sigungu.includes(q)), [regions, q]);
  const count = regions.filter((r) => picked.includes(r.sigungu)).reduce((a, r) => a + r.items, 0);
  const cash = man ? Number(man) * 10_000 : null;

  function finish() {
    saveProfile({ regions: picked, cash, purpose });
    router.replace("/home");
  }

  return (
    <main style={wrap}>
      <Progress step={step} />
      {step > 1 && (
        <button
          onClick={() => setStep(step - 1)}
          style={{
            border: 0,
            background: "none",
            textAlign: "left",
            color: "var(--muted)",
            fontSize: 14,
            padding: 0,
            marginBottom: 8,
            minHeight: 44,
          }}
        >
          {t.back} {t.step(step)}
        </button>
      )}

      {step === 1 && (
        <>
          <h1 style={h1}>{t.regionTitle}</h1>
          <p className="sub" style={{ fontSize: 15, margin: "0 0 16px" }}>
            {t.regionHint}
          </p>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t.regionSearch}
            style={{
              height: 48,
              borderRadius: 12,
              border: "1px solid var(--line)",
              padding: "0 14px",
              fontSize: 16,
              background: "var(--bg)",
              color: "var(--text)",
            }}
          />
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              marginTop: 14,
              overflowY: "auto",
              flexGrow: 1,
              alignContent: "flex-start",
            }}
          >
            {shown.map((r) => {
              const on = picked.includes(r.sigungu);
              return (
                <button
                  key={`${r.sido}-${r.sigungu}`}
                  onClick={() =>
                    setPicked(on ? picked.filter((x) => x !== r.sigungu) : [...picked, r.sigungu])
                  }
                  style={{
                    minHeight: 40,
                    padding: "0 12px",
                    borderRadius: 20,
                    border: on ? "2px solid var(--blue)" : "1px solid var(--line)",
                    background: on ? "var(--blue-soft)" : "var(--surface)",
                    fontSize: 14,
                  }}
                >
                  {r.sigungu} <span style={{ color: "var(--muted)", fontSize: 12 }}>{r.items}</span>
                </button>
              );
            })}
          </div>
          {picked.length > 0 && (
            <div style={{ fontSize: 13, color: "var(--green)", margin: "12px 0" }}>
              {t.count(count)}
            </div>
          )}
          <button className="btn primary" disabled={!picked.length} onClick={() => setStep(2)}>
            {t.next}
          </button>
        </>
      )}

      {step === 2 && (
        <>
          <h1 style={h1}>{t.cashTitle}</h1>
          <p className="sub" style={{ fontSize: 15, margin: "0 0 24px" }}>
            {t.cashHint}
          </p>
          <div
            style={{
              fontSize: 34,
              fontWeight: 700,
              borderBottom: "2px solid var(--blue)",
              paddingBottom: 10,
              minHeight: 56,
            }}
          >
            {cash ? won(cash) : ""}
            {!cash && <span style={{ color: "var(--faint)", fontSize: 22 }}>0{t.cashUnit}</span>}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            {[1000, 5000, 10000].map((add) => (
              <button
                key={add}
                onClick={() => setMan(String((Number(man) || 0) + add))}
                style={{
                  flexGrow: 1,
                  height: 40,
                  borderRadius: 10,
                  border: "1px solid var(--line)",
                  background: "var(--surface)",
                  fontSize: 14,
                }}
              >
                +{won(add * 10_000)}
              </button>
            ))}
          </div>
          <div style={{ flexGrow: 1 }} />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 4,
              marginBottom: 12,
            }}
          >
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "⌫"].map((k) => (
              <button
                key={k}
                aria-label={k === "⌫" ? "지우기" : k}
                onClick={() =>
                  setMan(k === "⌫" ? man.slice(0, -1) : (man + k).replace(/^0+/, "").slice(0, 7))
                }
                style={{ height: 52, border: 0, background: "transparent", fontSize: 22 }}
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
            style={{
              border: 0,
              background: "none",
              color: "var(--muted)",
              fontSize: 14,
              marginTop: 12,
              minHeight: 44,
            }}
          >
            {t.unsure}
          </button>
        </>
      )}

      {step === 3 && (
        <>
          <h1 style={h1}>{t.purposeTitle}</h1>
          <p className="sub" style={{ fontSize: 15, margin: "0 0 24px" }}>
            {t.purposeHint}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {(Object.keys(t.purposes) as Purpose[]).map((p) => (
              <button
                key={p}
                onClick={() => setPurpose(p)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  gap: 4,
                  padding: 20,
                  borderRadius: 16,
                  textAlign: "left",
                  border: purpose === p ? "2px solid var(--blue)" : "1px solid var(--line)",
                  background: purpose === p ? "var(--blue-soft)" : "var(--surface)",
                }}
              >
                <span style={{ fontSize: 18, fontWeight: 700 }}>{t.purposes[p][0]}</span>
                <span className="sub" style={{ fontSize: 14 }}>
                  {t.purposes[p][1]}
                </span>
              </button>
            ))}
          </div>
          <div style={{ flexGrow: 1 }} />
          <button className="btn primary" onClick={finish}>
            {t.done}
          </button>
        </>
      )}
    </main>
  );
}
