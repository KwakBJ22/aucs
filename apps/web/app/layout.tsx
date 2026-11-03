import type { Metadata, Viewport } from "next";
// 글꼴(11/4): Pretendard를 사이트에 같이 실어 어느 기기에서나 같은 모양. 쓰는 글자 묶음만 받아 가벼움
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";
import { copy } from "@/lib/copy.ko";
import { Providers } from "@/components/providers";

export const metadata: Metadata = { title: copy.appName, manifest: "/manifest.json" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f4f5f7" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
