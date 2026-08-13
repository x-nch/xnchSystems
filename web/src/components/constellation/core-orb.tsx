"use client";

import { cn } from "@/lib/utils/cn";

type CoreOrbProps = {
  size: number;
  selected: boolean;
  onSelect: () => void;
};

/** Central orchestrator orb — breathing halo + StatusPulse rings. */
export function CoreOrb({ size, selected, onSelect }: CoreOrbProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label="Select Nexi — system summary"
      className={cn(
        "group relative rounded-full outline-none transition-transform duration-300",
        "focus-visible:ring-2 focus-visible:ring-[#c8ff00]/70",
        selected ? "scale-[1.06]" : "hover:scale-[1.04]"
      )}
      style={{ width: size, height: size, ["--orb-size" as string]: `${size}px` }}
    >
      <span className="const-orb-halo absolute -inset-[18%] rounded-full bg-[radial-gradient(circle,rgba(200,255,0,0.22),transparent_70%)]" />
      <span className="const-pulse-ring" style={{ animationDelay: "0s" }} />
      <span className="const-pulse-ring" style={{ animationDelay: "1s" }} />
      <span className="const-pulse-ring" style={{ animationDelay: "2s" }} />
      <span className="const-core-dash absolute -inset-[7%] rounded-full" />

      <span
        className="relative flex h-full w-full flex-col items-center justify-center rounded-full border"
        style={{
          borderColor: "rgba(200,255,0,0.4)",
          background:
            "radial-gradient(circle at 34% 28%, rgba(200,255,0,0.34), rgba(7,8,6,0.96) 64%)",
          boxShadow: selected
            ? "0 0 0 1px rgba(200,255,0,0.7), 0 0 46px -6px rgba(200,255,0,0.6)"
            : "0 0 0 1px rgba(200,255,0,0.25), 0 0 34px -8px rgba(200,255,0,0.45)",
        }}
      >
        <span className="font-[family-name:var(--font-space-grotesk)] text-[calc(0.34*var(--orb-size))] font-bold tracking-[0.14em] text-[#c8ff00] [text-shadow:0_0_16px_rgba(200,255,0,0.6)]">
          NEXI
        </span>
        <span className="mt-[calc(0.05*var(--orb-size))] text-[calc(0.11*var(--orb-size))] font-medium uppercase tracking-[0.42em] text-[#8d9483]">
          orchestrator
        </span>
      </span>

      <span className="absolute -bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-[rgba(200,255,0,0.2)] bg-[rgba(11,13,9,0.9)] px-2 py-0.5 text-[10px] font-medium tracking-wide text-[#8d9483]">
        <span className="h-1.5 w-1.5 rounded-full bg-[#c8ff00]" style={{ boxShadow: "0 0 8px #c8ff00" }} />
        live
      </span>
    </button>
  );
}
