import { TabBar } from "@/components/tab-bar";
import { WatchProvider } from "@/components/watch-context";

export default function TabsLayout({ children }: { children: React.ReactNode }) {
  return (
    <WatchProvider>
      {children}
      <TabBar />
    </WatchProvider>
  );
}
