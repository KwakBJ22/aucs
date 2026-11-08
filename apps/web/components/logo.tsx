import { copy } from "@/lib/copy.ko";

// 옥스경매 로고(11/4). 휴대폰 어두운 화면에서는 「옥스」 글자가 흰 판(logo-dark)으로 — 어두운 색은 휴대폰에서만 씀(tokens.css).
// 높이는 자리마다 다르게(.logo-sm 머리·바닥, .logo-md 휴대폰 홈, .logo-lg 시작·로그인)
export function Logo({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  return (
    <picture className={`logo logo-${size}`}>
      <source
        srcSet="/brand/logo-dark.png"
        media="(prefers-color-scheme: dark) and (max-width: 1023px)"
      />
      <img src="/brand/logo.png" alt={copy.appName} width={973} height={240} />
    </picture>
  );
}
