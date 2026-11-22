"use client";

import { academyHit } from "@/lib/academy-hit";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { SAFE_MODE, type FindFilter, type FindStatus, type Source } from "@/lib/api/items";
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
    if (next) academyHit("safe"); // 아카데미 과제 「초보자 안전 모드」(11/18)
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

// ── PC 찾기 조건 칩 줄(11/22 디자인) ──
// 왼쪽 조건 칸 대신 칩 한 줄: 누르면 칩 아래 작은 창(안의 내용은 휴대폰 조건 칸과 같음).
// 고른 값이 있는 칩은 연한 파랑 + ✓ + 값(11/22 대표님 — 진한 바탕은 무거움). 한 번에 창 하나만.
type ChipKey =
  | "region"
  | "usage"
  | "price"
  | "area"
  | "days"
  | "failed"
  | "rate"
  | "source"
  | "status"
  | "safe";

const Down = ({ up }: { up?: boolean }) => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d={up ? "m6 15 6-6 6 6" : "m6 9 6 6 6-6"} />
  </svg>
);

export function FindChips({
  f,
  onChange,
  onSave,
  saveMsg,
  regions,
  source,
  onSource,
  status,
  onStatus,
}: {
  f: FindFilter;
  onChange: (f: FindFilter) => void;
  onSave?: () => void;
  saveMsg?: string;
  regions: string[];
  source: Source;
  onSource: (s: Source) => void;
  status: FindStatus;
  onStatus: (s: FindStatus) => void;
}) {
  const [open, setOpen] = useState<ChipKey | null>(null);
  const box = useRef<HTMLDivElement>(null);
  // 창 밖을 누르면 닫음
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const set = (p: Partial<FindFilter>) => onChange({ ...f, ...p });
  const toggle = (arr: string[] | undefined, k: string) =>
    (arr ?? []).includes(k) ? (arr ?? []).filter((x) => x !== k) : [...(arr ?? []), k];
  const ex = new Set(f.exclude ?? []);
  const allPicked = AVOID_KEYS.every((k) => ex.has(k));
  const opt = (list: [number | null, string][], v: number | undefined) =>
    v != null ? (list.find(([x]) => x === v)?.[1] ?? null) : null;
  const usageNames = (f.usage ?? []).map((u) => t.usages[u] ?? u);
  const area =
    f.area_min != null || f.area_max != null ? `${f.area_min ?? ""}~${f.area_max ?? ""}㎡` : null;

  // 칩마다 [이름, 고른 값(없으면 null)]
  const chips: [ChipKey, string, string | null][] = [
    [
      "region",
      t.chip.region,
      regions.length
        ? regions.length > 1
          ? t.chip.more(regions[0]!, regions.length - 1)
          : regions[0]!
        : null,
    ],
    [
      "usage",
      t.usage,
      usageNames.length
        ? usageNames.length > 1
          ? t.chip.more(usageNames[0]!, usageNames.length - 1)
          : usageNames[0]!
        : null,
    ],
    ["price", t.chip.price, f.price_max ? t.chip.priceV(f.price_max / EOK) : null],
    ["area", t.chip.area, area],
    ["days", t.days, opt(t.daysOpt, f.days_max)],
    ["failed", t.failed, opt(t.failedOpt, f.failed_min)],
    ["rate", t.rate, opt(t.rateOpt, f.rate_max)],
    ["source", t.sourceLabel, source !== "all" ? (t.source[source] ?? null) : null],
    ["status", t.chip.status, t.status[status] ?? null],
    ["safe", t.safe, ex.size ? `${t.safe} · ${ex.size}` : null],
  ];

  const body = (k: ChipKey) => {
    switch (k) {
      case "region":
        return (
          <>
            <p className="sub m-0">{regions.join(" · ") || t.chip.regionNone}</p>
            <Link href="/start" className="link">
              {t.chip.regionChange}
            </Link>
          </>
        );
      case "usage":
        return (
          <div className="pills">
            {Object.entries(t.usages).map(([k2, v]) => (
              <button
                key={k2}
                className={(f.usage ?? []).includes(k2) ? "on" : ""}
                onClick={() => set({ usage: toggle(f.usage, k2) })}
              >
                {v}
              </button>
            ))}
          </div>
        );
      case "price":
        return (
          <label className="d-flex ai-center gap-8">
            <input
              type="number"
              inputMode="decimal"
              min={0}
              step={0.5}
              aria-label={t.price}
              value={f.price_max != null ? f.price_max / EOK : ""}
              onChange={(e) =>
                set({
                  price_max: e.target.value ? Math.round(Number(e.target.value) * EOK) : undefined,
                })
              }
              className="f-input"
            />
            <span className="sub nowrap">{t.chip.priceUnit}</span>
          </label>
        );
      case "area":
        return (
          <div className="d-flex gap-6 ai-center">
            <input
              aria-label="최소 면적"
              type="number"
              min={0}
              className="f-input"
              value={f.area_min ?? ""}
              onChange={(e) =>
                set({ area_min: e.target.value ? Number(e.target.value) : undefined })
              }
            />
            ~
            <input
              aria-label="최대 면적"
              type="number"
              min={0}
              className="f-input"
              value={f.area_max ?? ""}
              onChange={(e) =>
                set({ area_max: e.target.value ? Number(e.target.value) : undefined })
              }
            />
            <span className="sub">㎡</span>
          </div>
        );
      case "days":
        return (
          <Pills
            opts={t.daysOpt}
            value={f.days_max ?? null}
            onPick={(v) => set({ days_max: v ?? undefined })}
          />
        );
      case "failed":
        return (
          <Pills
            opts={t.failedOpt}
            value={f.failed_min ?? null}
            onPick={(v) => set({ failed_min: v ?? undefined })}
          />
        );
      case "rate":
        return (
          <Pills
            opts={t.rateOpt}
            value={f.rate_max ?? null}
            onPick={(v) => set({ rate_max: v ?? undefined })}
          />
        );
      case "source":
        return (
          <Pills
            opts={(["all", "court", "onbid"] as Source[]).map(
              (s) => [s, t.source[s] ?? s] as [Source, string],
            )}
            value={source}
            onPick={(v) => onSource(v)}
          />
        );
      case "status":
        return (
          <Pills
            opts={Object.entries(t.status) as [FindStatus, string][]}
            value={status}
            onPick={(v) => onStatus(v)}
          />
        );
      case "safe":
        return (
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
              {Object.entries(t.avoids).map(([k2, v]) => (
                <button
                  key={k2}
                  className={ex.has(k2) ? "on" : ""}
                  aria-pressed={ex.has(k2)}
                  onClick={() => set({ exclude: toggle(f.exclude, k2) })}
                >
                  {v}
                </button>
              ))}
            </div>
          </>
        );
    }
  };

  const any = Object.keys(f).length > 0;
  return (
    <div className="find-chips" ref={box}>
      {chips.map(([k, name, val]) => (
        <div key={k} className="fc-wrap">
          <button
            className={`fc-chip${val ? " on" : ""}${open === k ? " open" : ""}`}
            aria-expanded={open === k}
            onClick={() => {
              if (open !== k && k === "safe") academyHit("safe"); // 아카데미 과제 「초보자 안전 모드」(11/18)
              setOpen(open === k ? null : k);
            }}
          >
            {val && (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="m5 12 5 5 9-10" />
              </svg>
            )}
            {val ?? name}
            <Down up={open === k} />
          </button>
          {open === k && (
            <div className="fc-pop" role="dialog" aria-label={name}>
              <div className="fc-pop-title">{name}</div>
              {body(k)}
            </div>
          )}
        </div>
      ))}
      {any && (
        <button className="fc-text" onClick={() => onChange({})}>
          {t.condReset}
        </button>
      )}
      {onSave && (
        <button className="fc-text blue" onClick={onSave}>
          {t.saveCond}
        </button>
      )}
      {saveMsg && <span className="sub">{saveMsg}</span>}
    </div>
  );
}
