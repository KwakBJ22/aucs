"use client";

import { useState } from "react";
import { copyText } from "@/lib/copy-text";
import { goLink, iros, type GoItem, type GoKey } from "@/lib/go-links";
import { t } from "@/components/item/shared";

// 바로 가기 한 줄(11/20): 그 칸을 확인할 공식 · 시세 사이트. 주소가 미리 안 들어가는 곳은 누를 때 주소를 복사함
export function GoLinks({ keys, d }: { keys: GoKey[]; d: GoItem }) {
  const [copied, setCopied] = useState(false);
  const list = keys.map((k) => goLink(k, d)).filter((x) => x != null);
  if (!list.length) return null;
  return (
    <div className="mt-4">
      <div className="d-flex f-wrap gap-12">
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
      </div>
      {copied && <p className="sub fs-sm m-0">{t.go.copied}</p>}
    </div>
  );
}
