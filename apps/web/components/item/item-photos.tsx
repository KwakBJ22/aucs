"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { copy } from "@/lib/copy.ko";

const c = copy.photos;

// 법원 현장 사진(11/1, 11/11 대표님): 줄 양끝 꺽쇠로 넘기기 · 누르면 크게 — 좌우 가운데 꺽쇠, 아래 「‹ 1/12 ›」, 키보드 ←→ · 손가락으로 밀기
export function ItemPhotos({ list }: { list?: string[] }) {
  const [big, setBig] = useState<number | null>(null);
  const strip = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState({ left: false, right: false });

  const measure = useCallback(() => {
    const el = strip.current;
    if (!el) return;
    setEdge({
      left: el.scrollLeft > 4,
      right: el.scrollLeft + el.clientWidth < el.scrollWidth - 4,
    });
  }, []);
  useEffect(() => {
    measure();
    const el = strip.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [measure, list]);

  const n = list?.length ?? 0;
  const go = useCallback((d: number) => setBig((i) => (i === null ? i : (i + d + n) % n)), [n]);
  useEffect(() => {
    if (big === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "Escape") setBig(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [big, go]);
  const touchX = useRef<number | null>(null);

  if (!list?.length) return null;
  const slide = (d: number) => {
    const el = strip.current;
    if (el) el.scrollBy({ left: d * el.clientWidth * 0.8, behavior: "smooth" });
  };
  return (
    <>
      <div className="photo-strip-wrap mt-10">
        <div
          className="photo-strip quiet-scroll"
          ref={strip}
          onScroll={measure}
          aria-label={c.label}
        >
          {list.map((u, i) => (
            <button
              key={u}
              onClick={() => setBig(i)}
              className="photo-thumb"
              aria-label={`${c.label} ${i + 1}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- Storage 사진은 이미 작게 줄여 둠 */}
              <img src={u} alt="" loading="lazy" />
            </button>
          ))}
        </div>
        {edge.left && (
          <button className="photo-arrow left" aria-label={c.prev} onClick={() => slide(-1)}>
            ‹
          </button>
        )}
        {edge.right && (
          <button className="photo-arrow right" aria-label={c.next} onClick={() => slide(1)}>
            ›
          </button>
        )}
      </div>
      <div className="sub fs-xs mt-4">{c.count(n)}</div>
      {big !== null && (
        <div
          className="photo-viewer"
          role="dialog"
          aria-label={c.label}
          onClick={() => setBig(null)}
          onTouchStart={(e) => (touchX.current = e.touches[0]?.clientX ?? null)}
          onTouchEnd={(e) => {
            const x0 = touchX.current;
            touchX.current = null;
            if (x0 === null) return;
            const dx = (e.changedTouches[0]?.clientX ?? x0) - x0;
            if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={list[big]} alt="" onClick={(e) => e.stopPropagation()} />
          <button className="pv-close" aria-label={c.close} onClick={() => setBig(null)}>
            ×
          </button>
          {n > 1 && (
            <>
              <button
                className="pv-side left"
                aria-label={c.prev}
                onClick={(e) => (e.stopPropagation(), go(-1))}
              >
                ‹
              </button>
              <button
                className="pv-side right"
                aria-label={c.next}
                onClick={(e) => (e.stopPropagation(), go(1))}
              >
                ›
              </button>
              <div className="pv-bar" onClick={(e) => e.stopPropagation()}>
                <button aria-label={c.prev} onClick={() => go(-1)}>
                  ‹
                </button>
                <span className="num">{c.pos(big + 1, n)}</span>
                <button aria-label={c.next} onClick={() => go(1)}>
                  ›
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
