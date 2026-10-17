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
    <main style={{ maxWidth: 420, margin: "0 auto", padding: "32px 20px" }}>
      <h1 style={{ fontSize: 28, margin: "0 0 24px" }}>{copy.appName}</h1>
      <HealthRow label={copy.health.api} state={api} />
      <HealthRow label={copy.health.db} state={db} />
    </main>
  );
}
