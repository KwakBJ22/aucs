"use client";

import { useState } from "react";
import { SAFE_MODE, type FindFilter } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";

const t = copy.find;
const EOK = 100_000_000;

function Pills<T extends string | number | null>({
  opts,
  value,
  onPick,
}: {
  opts: [T, string][];
  value: T;
  onPick: (v: T) => void;
}) {
  return (
    <div className="pills">
      {opts.map(([v, label]) => (
        <button key={String(v)} className={value === v ? "on" : ""} onClick={() => onPick(v)}>
          {label}
        </button>
      ))}
    </div>
  );
}

// 찾기 조건(FIND-03): 종류·가격·면적·기일·유찰·감정가 대비, 초보자 안전 모드, 피하고 싶은 것, 저장+알림
export function FindFilters({
  f,
  onChange,
  onSave,
  saveMsg,
}: {
  f: FindFilter;
  onChange: (f: FindFilter) => void;
  onSave?: () => void;
  saveMsg?: string;
}) {
  const ex = new Set(f.exclude ?? []);
  const safe = SAFE_MODE.every((k) => ex.has(k));
  const [own, setOwn] = useState(!safe && ex.size > 0);
  const set = (p: Partial<FindFilter>) => onChange({ ...f, ...p });
  const toggle = (arr: string[] | undefined, k: string) =>
    (arr ?? []).includes(k) ? (arr ?? []).filter((x) => x !== k) : [...(arr ?? []), k];

  return (
    <div className="filters">
      <div className="f-block">
        <div className="f-label">{t.usage}</div>
        <div className="pills">
          {Object.entries(t.usages).map(([k, v]) => (
            <button key={k} className={(f.usage ?? []).includes(k) ? "on" : ""} onClick={() => set({ usage: toggle(f.usage, k) })}>
              {v}
            </button>
          ))}
        </div>
      </div>
      <div className="f-block">
        <label className="f-label" htmlFor="f-price">
          {t.price}
        </label>
        <input
          id="f-price"
          type="number"
          inputMode="decimal"
          min={0}
          step={0.5}
          value={f.price_max != null ? f.price_max / EOK : ""}
          onChange={(e) => set({ price_max: e.target.value ? Math.round(Number(e.target.value) * EOK) : undefined })}
          className="f-input"
        />
      </div>
      <div className="f-block">
        <div className="f-label">{t.area}</div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input aria-label="최소 면적" type="number" min={0} className="f-input" value={f.area_min ?? ""} onChange={(e) => set({ area_min: e.target.value ? Number(e.target.value) : undefined })} />
          ~
          <input aria-label="최대 면적" type="number" min={0} className="f-input" value={f.area_max ?? ""} onChange={(e) => set({ area_max: e.target.value ? Number(e.target.value) : undefined })} />
        </div>
      </div>
      <div className="f-block">
        <div className="f-label">{t.days}</div>
        <Pills opts={t.daysOpt} value={f.days_max ?? null} onPick={(v) => set({ days_max: v ?? undefined })} />
      </div>
      <div className="f-block">
        <div className="f-label">{t.failed}</div>
        <Pills opts={t.failedOpt} value={f.failed_min ?? null} onPick={(v) => set({ failed_min: v ?? undefined })} />
      </div>
      <div className="f-block">
        <div className="f-label">{t.rate}</div>
        <Pills opts={t.rateOpt} value={f.rate_max ?? null} onPick={(v) => set({ rate_max: v ?? undefined })} />
      </div>
      <div className="f-block">
        <label className="switch-row">
          <span>
            <b>{t.safe}</b>
            <span className="sub" style={{ display: "block" }}>
              {t.safeSub}
            </span>
          </span>
          <input
            type="checkbox"
            role="switch"
            checked={safe}
            onChange={() => {
              setOwn(false);
              set({ exclude: safe ? [] : Array.from(new Set([...(f.exclude ?? []), ...SAFE_MODE])) });
            }}
          />
        </label>
        <button className="link-btn" onClick={() => setOwn(!own)}>
          {t.avoid} {own ? "▴" : "›"}
        </button>
        {own && (
          <div className="pills" style={{ marginTop: 6 }}>
            {Object.entries(t.avoids).map(([k, v]) => (
              <button key={k} className={ex.has(k) ? "on" : ""} onClick={() => set({ exclude: toggle(f.exclude, k) })}>
                {v} {ex.has(k) ? "빼기" : ""}
              </button>
            ))}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="chip gray" style={{ border: 0, minHeight: 36 }} onClick={() => onChange({})}>
          {t.condReset}
        </button>
        {onSave && (
          <button className="chip green" style={{ border: 0, minHeight: 36 }} onClick={onSave}>
            {t.saveCond}
          </button>
        )}
      </div>
      {saveMsg && <div className="sub">{saveMsg}</div>}
    </div>
  );
}

// 고른 조건을 짧게(휴대폰 접힌 줄에 보여 줌)
export function filterSummary(f: FindFilter): string {
  const out: string[] = [];
  (f.usage ?? []).forEach((u) => out.push(t.usages[u] ?? u));
  if (f.price_max) out.push(`${f.price_max / EOK}억까지`);
  if (f.days_max) out.push(t.daysOpt.find(([v]) => v === f.days_max)?.[1] ?? "");
  if (f.failed_min) out.push(`유찰 ${f.failed_min}회+`);
  if (f.rate_max) out.push(`${f.rate_max}% 이하`);
  const ex = f.exclude ?? [];
  if (SAFE_MODE.every((k) => ex.includes(k))) out.push("안전 모드");
  else if (ex.length) out.push(`빼기 ${ex.length}`);
  return out.filter(Boolean).join(" · ");
}
