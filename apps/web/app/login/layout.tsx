import { AppShell } from "@/components/layout/app-shell";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
