"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { loadProfile } from "@/lib/profile";

// 처음 온 사람은 시작 질문으로, 답한 사람은 홈으로.
export default function Root() {
  const router = useRouter();
  useEffect(() => {
    router.replace(loadProfile() ? "/home" : "/start");
  }, [router]);
  return null;
}
