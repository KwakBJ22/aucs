"use client";

import { useWatch } from "./watch-context";
import { copy } from "@/lib/copy.ko";

// inline: 글자 줄 옆(상세 머리 「작업 공간」 곁)에서는 가운데 맞춤 — 카드 귀퉁이에서는 위·오른쪽(11/11)
export function HeartButton({ id, inline = false }: { id: string; inline?: boolean }) {
  const { ids, toggle } = useWatch();
  const on = ids.has(id);
  return (
    <button
      aria-label={on ? copy.watch.remove : copy.watch.add}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        void toggle(id);
      }}
      className={`icon-btn d-flex p-4 ${inline ? "ai-center jc-center" : "ai-start jc-end"}`}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill={on ? "var(--red)" : "none"}
        stroke={on ? "var(--red)" : "var(--faint)"}
        strokeWidth="1.8"
        aria-hidden="true"
      >
        <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
      </svg>
    </button>
  );
}
