import { Delayed, SkHeader, SkRows } from "@/components/skeleton";

// 관리자 화면 판(11/4)
export default function Loading() {
  return (
    <main className="page">
      <Delayed>
        <SkHeader />
        <SkRows n={6} />
      </Delayed>
    </main>
  );
}
