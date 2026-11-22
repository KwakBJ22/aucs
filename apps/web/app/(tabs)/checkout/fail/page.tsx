"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { payApi } from "@/lib/api/me";
import { useSession } from "@/lib/auth";
import { copy } from "@/lib/copy.ko";

const t = copy.checkout;

// 결제창에서 그만두거나 실패해 돌아온 곳(11/23 미리 구성): ?code&message&orderId(그만두면 orderId 없음).
// 주문에 실패를 적어 둠(이용권 · 돈은 그대로).
function Fail() {
  const sp = useSearchParams();
  const { session } = useSession();
  const code = sp.get("code") ?? "";
  const message = sp.get("message") ?? "";
  const oid = sp.get("orderId");
  const sent = useRef(false);
  const canceled = code === "PAY_PROCESS_CANCELED" || code === "USER_CANCEL";

  useEffect(() => {
    if (!session || !oid || sent.current) return;
    sent.current = true;
    payApi.fail(session.access_token, { order_id: oid, code, message }).catch(() => undefined);
  }, [session, oid, code, message]);

  return (
    <main className="page narrow checkout">
      <PageHeader title={t.title} />
      <section className="section ta-center py-32 px-18">
        <h2 className="co-title">{canceled ? t.fail.canceled : t.fail.failed}</h2>
        <p className="sub">{canceled ? t.fail.canceledSub : message}</p>
        <Link href="/plans" className="btn primary mt-12">
          {t.done.again}
        </Link>
        {!canceled && (
          <Link href="/more" className="link d-block mt-12">
            {t.done.ask}
          </Link>
        )}
      </section>
    </main>
  );
}

export default function CheckoutFailPage() {
  return (
    <Suspense>
      <Fail />
    </Suspense>
  );
}
