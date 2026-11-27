"use client";

import { useEffect, useState } from "react";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.lotAlert;

// 같은 단지 경매 알림(11/28, 예정물건 3단계): 이 단지에 새 사건(공고 전) · 새 매각공고가 들어오면 알림
export function LotAlert({ id }: { id: string }) {
  const { session } = useSession();
  const token = session?.access_token ?? null;
  const [on, setOn] = useState<boolean | null>(null);

  useEffect(() => {
    if (!token) return;
    meApi
      .lotWatch(token, id)
      .then((r) => setOn(r.on))
      .catch(() => {});
  }, [token, id]);

  const toggle = () => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    const next = !on;
    setOn(next);
    meApi.setLotWatch(token, id, next).catch(() => setOn(!next));
  };

  return (
    <button className="btn soft w-full mt-10" onClick={toggle} aria-pressed={Boolean(on)}>
      {on ? t.on : t.off}
    </button>
  );
}
