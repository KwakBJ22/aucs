import { Delayed, SkHeader, SkTable } from "@/components/skeleton";

// 전문가 화면으로 넘어갈 때 깔리는 표 모양 판(11/4)
export default function Loading() {
  return (
    <main className="page">
      <Delayed>
        <SkHeader />
        <SkTable />
      </Delayed>
    </main>
  );
}
