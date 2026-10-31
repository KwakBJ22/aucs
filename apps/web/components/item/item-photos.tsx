"use client";

import { useState } from "react";
import { copy } from "@/lib/copy.ko";

// 법원 현장 사진(11/1): 옆으로 넘겨 보는 줄, 누르면 크게. 매각 뒤 30일 지나면 서버가 안 보내서 줄도 없음
export function ItemPhotos({ list }: { list?: string[] }) {
  const [big, setBig] = useState<string | null>(null);
  if (!list?.length) return null;
  return (
    <>
      <div
        className="d-flex gap-6 ox-auto quiet-scroll mt-10"
        aria-label={copy.photos.label}
        style={{ scrollSnapType: "x mandatory" }}
      >
        {list.map((u, i) => (
          <button
            key={u}
            onClick={() => setBig(u)}
            className="b-0 p-0 bg-none r-12"
            style={{ flex: "0 0 auto", scrollSnapAlign: "start" }}
            aria-label={`${copy.photos.label} ${i + 1}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- Storage 사진은 이미 작게 줄여 둠 */}
            <img
              src={u}
              alt=""
              loading="lazy"
              className="r-12 d-block"
              style={{ height: 120, width: "auto", objectFit: "cover", background: "var(--panel)" }}
            />
          </button>
        ))}
      </div>
      <div className="sub fs-xs mt-4">{copy.photos.count(list.length)}</div>
      {big && (
        <div
          onClick={() => setBig(null)}
          className="pos-fixed d-flex ai-center"
          style={{ inset: 0, zIndex: 60, background: "rgba(0,0,0,0.85)", justifyContent: "center" }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={big} alt="" style={{ maxWidth: "100%", maxHeight: "100%" }} />
        </div>
      )}
    </>
  );
}
