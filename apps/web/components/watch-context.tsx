"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { meApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";

type WatchState = { ids: Set<string>; token: string | null; toggle: (id: string) => Promise<void> };
const Ctx = createContext<WatchState>({ ids: new Set(), token: null, toggle: async () => {} });

// 관심 담은 물건 id 를 한 번 불러와 모든 카드가 같이 씀.
export function WatchProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const token = session?.access_token ?? null;
  const [ids, setIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!token) return;
    meApi
      .watchIds(token)
      .then((xs) => setIds(new Set(xs)))
      .catch(() => {});
  }, [token]);

  const toggle = useCallback(
    async (id: string) => {
      if (!token) {
        window.location.href = "/login";
        return;
      }
      const on = ids.has(id);
      setIds((s) => {
        const n = new Set(s);
        if (on) n.delete(id);
        else n.add(id);
        return n;
      });
      await (on ? meApi.removeWatch(token, id) : meApi.addWatch(token, id));
    },
    [ids, token],
  );

  return <Ctx.Provider value={{ ids, token, toggle }}>{children}</Ctx.Provider>;
}

export const useWatch = () => useContext(Ctx);
