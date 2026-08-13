"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { SettingsModal } from "@/components/settings/settings-modal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GatewayQuerySync } from "@/components/layout/gateway-query-sync";
import { useHydrated } from "@/lib/hooks/use-hydrated";

/** Routes rendered without control-surface chrome (standalone landing pages). */
const STANDALONE_ROUTES = ["/constellation"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const hydrated = useHydrated();
  const pathname = usePathname();
  const standalone =
    STANDALONE_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`));

  if (standalone) {
    return <TooltipProvider delayDuration={250}>{children}</TooltipProvider>;
  }

  return (
    <TooltipProvider delayDuration={250}>
      <div className="flex h-dvh overflow-hidden bg-background text-foreground">
        {hydrated ? (
          <>
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Topbar onOpenSettings={() => setSettingsOpen(true)} />
              <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
            </div>
          </>
        ) : (
          <div className="flex min-h-0 w-full items-center justify-center">
            <span className="font-mono text-[12px] text-muted-foreground">
              Loading…
            </span>
          </div>
        )}
        <SettingsModal open={settingsOpen} onOpenChange={setSettingsOpen} />
        <GatewayQuerySync />
      </div>
    </TooltipProvider>
  );
}
