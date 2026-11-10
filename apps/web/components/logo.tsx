import { copy } from "@/lib/copy.ko";

// 옥스경매 로고(11/4). 화면은 늘 밝게(11/10 — 휴대폰 어두운 화면을 뺌).
// 높이는 자리마다 다르게(.logo-sm 머리·바닥, .logo-md 휴대폰 홈, .logo-lg 시작·로그인)
export function Logo({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  return (
    <picture className={`logo logo-${size}`}>
      <img src="/brand/logo.png" alt={copy.appName} width={973} height={240} />
    </span>
  );
}
