"use client";

import { useState, type ReactNode } from "react";
import { copyText } from "@/lib/copy-text";
import { goLink, iros, type GoItem, type GoKey } from "@/lib/go-links";
import { t } from "@/components/item/shared";

// 바로 가기 한 줄(11/20): 그 칸을 확인할 공식 · 시세 사이트. 주소가 미리 안 들어가는 곳은 누를 때 주소를 복사함
// inline(11/22 디자인 PC): 값 바로 뒤에 붙여 씀(「제3종일반주거지역 토지이음 ›」)
// lead: 같은 줄 맨 앞에 둘 링크(「실거래 전체 보기」 — 따로 두면 줄 높이가 어긋났음, 11/24)
export function GoLinks({
  keys,
  d,
  inline,
  lead,
}: {
  keys: GoKey[];
  d: GoItem;
  inline?: boolean;
  lead?: ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const list = keys.map((k) => goLink(k, d)).filter((x) => x != null);
  if (!list.length && !lead) return null;
  const Box = inline ? "span" : "div";
  return (
    <Box className={inline ? "go-inline" : "mt-4"}>
      <Box className={inline ? "" : "d-flex f-wrap gap-12"}>
        {lead}
        {list.map((x) => (
          <a
            key={x.key}
            className="link fs-sm"
            href={x.href}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              if (x.key === "iros") e.currentTarget.href = iros();
              if (!x.filled && d.address) void copyText(d.address).then(setCopied);
            }}
          >
            {t.go[x.key]}
          </a>
        ))}
      </Box>
      {copied && !inline && <p className="sub fs-sm m-0">{t.go.copied}</p>}
    </Box>
  );
}
