import type { Metadata, Viewport } from "next";
import "./globals.css";
import { copy } from "@/lib/copy.ko";
import { Providers } from "@/components/providers";

export const metadata: Metadata = { title: copy.appName, manifest: "/manifest.json" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f4f5f7" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
