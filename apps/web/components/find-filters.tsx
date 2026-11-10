"use client";

import { useEffect, useState } from "react";
import { SAFE_MODE, type FindFilter } from "@/lib/api/items";
import { copy } from "@/lib/copy.ko";

const t = copy.find;
const EOK = 100_000_000;
const KEY_SAFE_OPEN = "aucs_find_safe_open";
const AVOID_KEYS = Object.keys(t.avoids);

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
  const allPicked = AVOID_KEYS.every((k) => ex.has(k));
  // 여닫음은 이 기기에 기억(찾기 화면의 다른 조건과 같은 방식) — 닫아도 고른 것은 그대로
  const [safeOpen, setSafeOpen] = useState(false);
  useEffect(() => {
    try {
      setSafeOpen(localStorage.getItem(KEY_SAFE_OPEN) === "1");
    } catch {
      /* 못 읽어도 계속 */
    }
  }, []);
  const toggleSafeOpen = () => {
    const next = !safeOpen;
    setSafeOpen(next);
    try {
      localStorage.setItem(KEY_SAFE_OPEN, next ? "1" : "0");
    } catch {
      /* 저장 못 해도 계속 */
    }
  };
  const set = (p: Partial<FindFilter>) => onChange({ ...f, ...p });
  const toggle = (arr: string[] | undefined, k: string) =>
    (arr ?? []).includes(k) ? (arr ?? []).filter((x) => x !== k) : [...(arr ?? []), k];

  return (
    <div className="filters">
      <div className="f-block">
        <div className="f-label">{t.usage}</div>
        <div className="pills">
          {Object.entries(t.usages).map(([k, v]) => (
            <button
              key={k}
              className={(f.usage ?? []).includes(k) ? "on" : ""}
              onClick={() => set({ usage: toggle(f.usage, k) })}
            >
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
          onChange={(e) =>
            set({
              price_max: e.target.value ? Math.round(Number(e.target.value) * EOK) : undefined,
            })
          }
          className="f-input"
        />
      </div>
      <div className="f-block">
        <div className="f-label">{t.area}</div>
        <div className="d-flex gap-6 ai-center">
          <input
            aria-label="최소 면적"
            type="number"
            min={0}
            className="f-input"
            value={f.area_min ?? ""}
            onChange={(e) => set({ area_min: e.target.value ? Number(e.target.value) : undefined })}
          />
          ~
          <input
            aria-label="최대 면적"
            type="number"
            min={0}
            className="f-input"
            value={f.area_max ?? ""}
            onChange={(e) => set({ area_max: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>
      </div>
      <div className="f-block">
        <div className="f-label">{t.days}</div>
        <Pills
          opts={t.daysOpt}
          value={f.days_max ?? null}
          onPick={(v) => set({ days_max: v ?? undefined })}
        />
      </div>
      <div className="f-block">
        <div className="f-label">{t.failed}</div>
        <Pills
          opts={t.failedOpt}
          value={f.failed_min ?? null}
          onPick={(v) => set({ failed_min: v ?? undefined })}
        />
      </div>
      <div className="f-block">
        <div className="f-label">{t.rate}</div>
        <Pills
          opts={t.rateOpt}
          value={f.rate_max ?? null}
          onPick={(v) => set({ rate_max: v ?? undefined })}
        />
      </div>
      <div className="f-block">
        <button
          className="line-row fold w-full ta-left"
          aria-expanded={safeOpen}
          onClick={toggleSafeOpen}
        >
          <span>
            <b>{t.safe}</b>
            {ex.size > 0 && <span className="sub ml-6">{t.safePicked(ex.size)}</span>}
          </span>
        </button>
        {safeOpen && (
          <>
            <div className="d-flex jc-between ai-center gap-8">
              <span className="sub">{t.safeHint}</span>
              <button
                className="btn secondary sm"
                onClick={() => set({ exclude: allPicked ? [] : AVOID_KEYS })}
              >
                {allPicked ? t.safeNone : t.safeAll}
              </button>
            </div>
            <div className="pills mt-10">
              {Object.entries(t.avoids).map(([k, v]) => (
                <button
                  key={k}
                  className={ex.has(k) ? "on" : ""}
                  aria-pressed={ex.has(k)}
                  onClick={() => set({ exclude: toggle(f.exclude, k) })}
                >
                  {v}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      <div className="d-flex gap-8 f-wrap">
        <button className="btn secondary sm" onClick={() => onChange({})}>
          {t.condReset}
        </button>
        {onSave && (
          <button className="btn soft sm" onClick={onSave}>
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
