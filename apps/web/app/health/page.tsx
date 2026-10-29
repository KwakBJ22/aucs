"use client";

import { useEffect, useState } from "react";
import { HealthRow } from "@/components/health-row";
import { checkApi, checkDb, type HealthState } from "@/lib/api/health";
import { copy } from "@/lib/copy.ko";

export default function HomePage() {
  const [api, setApi] = useState<HealthState>("checking");
  const [db, setDb] = useState<HealthState>("checking");

  useEffect(() => {
    void checkApi().then(setApi);
    void checkDb().then(setDb);
  }, []);

  return (
    <main className="my-0 mx-auto py-32 px-20" style={{ maxWidth: 420 }}>
      <h1 className="fs-3xl mt-0 mb-24 mx-0">{copy.appName}</h1>
      <HealthRow label={copy.health.api} state={api} />
      <HealthRow label={copy.health.db} state={db} />
    </main>
  );
}
