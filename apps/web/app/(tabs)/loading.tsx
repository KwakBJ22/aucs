import { SkListPage } from "@/components/skeleton";

// 화면을 넘어갈 때 다음 화면 코드가 오기 전까지 깔리는 판(11/4)
export default function Loading() {
  return (
    <main className="page">
      <SkListPage />
    </main>
  );
}
