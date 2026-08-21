"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ParticleHumanoid } from "./particle-humanoid";
import { Waveform } from "@/components/network/waveform";
import { useUiStore } from "@/lib/stores/ui-store";

export function PresenceView() {
  const router = useRouter();
  const setPresenceTransitioning = useUiStore((s) => s.setPresenceTransitioning);

  useEffect(() => {
    setPresenceTransitioning(false);
  }, [setPresenceTransitioning]);

  return (
    <div className="presence-enter relative h-full w-full overflow-hidden bg-[#020617]">
      <div className="hud-grid absolute inset-0 opacity-30" />

      {/* ambient core glow */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(245,197,24,0.12) 0%, rgba(34,211,238,0.08) 35%, transparent 68%)",
        }}
        aria-hidden
      />

      <ParticleHumanoid />

      <div className="pointer-events-none absolute inset-0 z-10 vignette" aria-hidden />

      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="absolute left-4 top-4 flex flex-col gap-2">
          <div className="hud-panel rounded-lg px-3 py-2">
            <span className="glow-text font-mono text-[10px] font-semibold uppercase tracking-[0.32em] text-cyan-200">
              Presence
            </span>
            <span className="mt-0.5 block text-[10px] text-muted-foreground">
              humanoid interface · particle field
            </span>
          </div>
          <Waveform className="h-6 w-32 opacity-50" />
        </div>

        <div className="absolute bottom-4 left-4 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">
          tracking subsystem online
        </div>

        <div className="pointer-events-auto absolute bottom-4 right-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/")}
            className="border-cyan-300/20 bg-card/70 backdrop-blur hover:bg-card"
          >
            <X className="h-3.5 w-3.5" />
            Exit to network
          </Button>
        </div>
      </div>
    </div>
  );
}
