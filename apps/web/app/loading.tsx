import { SkListPage } from "@/components/skeleton";

// 맨 처음 들어올 때·시작·로그인 화면으로 넘어갈 때 깔리는 판(11/4)
export default function Loading() {
  return (
    <main className="page">
      <SkListPage />
    </main>
  );
}
