"use client";

import { cn } from "@/lib/utils/cn";
import type { AgentSpec } from "@/lib/constellation/data";

type AgentOrbProps = {
  agent: AgentSpec;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
};

const STATE_COLOR: Record<AgentSpec["status"]["state"], string> = {
  online: "#8d9483",
  active: "#c8ff00",
  standby: "#6f7566",
  blocked: "#c8ff00",
};

export function AgentOrb({ agent, selected, dimmed, onSelect }: AgentOrbProps) {
  const Icon = agent.icon;
  const isGate = agent.isGate;
  const isBlocked = agent.status.state === "blocked";

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`Select ${agent.name} — ${agent.role}`}
      aria-pressed={selected}
      className={cn(
        "group relative rounded-full outline-none transition-all duration-300",
        "focus-visible:ring-2 focus-visible:ring-[#c8ff00]/70",
        isGate ? "rounded-[22%]" : "rounded-full",
        selected
          ? "const-node-focus"
          : dimmed
            ? "scale-[0.96] opacity-35 saturate-50"
            : "const-node-drift hover:scale-[1.06]",
        !selected && !dimmed && "hover:opacity-100"
      )}
      style={{ width: agent.weight * 92, height: agent.weight * 92, ["--orb" as string]: `${agent.weight * 92}px` }}
    >
      {isGate && (
        <span className="const-gate-beacon absolute -inset-[14%] rounded-[28%] border border-[rgba(200,255,0,0.5)]" />
      )}
      {isBlocked && (
        <span className="const-pulse-ring" style={{ animationDelay: "0.4s" }} />
      )}

      <span
        className={cn(
          "relative flex h-full w-full flex-col items-center justify-center gap-1 overflow-hidden border bg-[rgba(11,13,9,0.9)] backdrop-blur-sm",
          isGate ? "rounded-[22%]" : "rounded-full"
        )}
        style={{
          borderColor: selected
            ? "rgba(200,255,0,0.75)"
            : isGate
              ? "rgba(200,255,0,0.45)"
              : "rgba(200,255,0,0.16)",
        }}
      >
        <span
          className="pointer-events-none absolute inset-0"
          style={{
            background: isGate
              ? "radial-gradient(circle at 50% 35%, rgba(200,255,0,0.14), transparent 70%)"
              : "radial-gradient(circle at 50% 38%, rgba(200,255,0,0.07), transparent 72%)",
          }}
        />
        <span
          className={cn(
            "relative flex items-center justify-center rounded-full",
            isGate ? "rounded-[18%] bg-[rgba(200,255,0,0.12)]" : "bg-[rgba(200,255,0,0.08)]"
          )}
          style={{ width: "34%", height: "34%" }}
        >
          <Icon
            className="text-[#c8ff00]"
            style={{ width: "52%", height: "52%" }}
            strokeWidth={1.6}
          />
        </span>
        <span
          className="relative max-w-[86%] truncate text-center font-[family-name:var(--font-space-grotesk)] font-semibold leading-tight text-[#eef2e2]"
          style={{ fontSize: "calc(var(--orb) * 0.145)" }}
        >
          {agent.name}
        </span>
        <span
          className="relative max-w-[86%] truncate text-center font-medium uppercase tracking-[0.14em] text-[#6f7566]"
          style={{ fontSize: "calc(var(--orb) * 0.082)" }}
        >
          {agent.role}
        </span>
      </span>

      <span
        className={cn(
          "absolute left-1/2 flex -translate-x-1/2 items-center gap-1.5 whitespace-nowrap rounded-full border border-[rgba(200,255,0,0.18)] bg-[rgba(7,8,6,0.92)] px-2 py-0.5 text-[10px] font-medium tracking-wide",
          isGate ? "top-0 -translate-y-1/2 text-[#c8ff00]" : "-bottom-1.5 text-[#8d9483]"
        )}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: STATE_COLOR[agent.status.state], boxShadow: `0 0 7px ${STATE_COLOR[agent.status.state]}` }}
        />
        {agent.status.metric}
      </span>
    </button>
  );
}
