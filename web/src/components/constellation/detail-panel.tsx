"use client";

import { X } from "lucide-react";
import { AGENTS, CORE_ID, CORE_SUMMARY } from "@/lib/constellation/data";

type DetailPanelProps = {
  selected: string | null;
  onClose: () => void;
};

export function DetailPanel({ selected, onClose }: DetailPanelProps) {
  if (!selected) return null;

  const agent = AGENTS.find((a) => a.id === selected);
  const isCore = selected === CORE_ID;

  const stateColor =
    agent?.status.state === "blocked"
      ? "#c8ff00"
      : agent?.status.state === "active"
        ? "#c8ff00"
        : agent?.status.state === "standby"
          ? "#6f7566"
          : "#8d9483";

  return (
    <div
      key={selected}
      className="const-panel-in absolute right-6 top-1/2 z-30 w-[min(320px,90vw)] -translate-y-1/2"
    >
      <div className="rounded-xl border border-[rgba(200,255,0,0.18)] bg-[rgba(7,8,6,0.92)] p-5 shadow-[0_0_40px_-12px_rgba(200,255,0,0.35)] backdrop-blur-md">
        <div className="flex items-start justify-between gap-3">
          <div>
            {!isCore && agent && (
              <span className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border border-[rgba(200,255,0,0.2)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-[#8d9483]">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: stateColor, boxShadow: `0 0 7px ${stateColor}` }}
                />
                {agent.status.metric}
              </span>
            )}
            <h3 className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold tracking-tight text-[#c8ff00]">
              {isCore ? CORE_SUMMARY.name : agent?.name}
            </h3>
            <p className="mt-0.5 text-[11px] font-medium uppercase tracking-[0.24em] text-[#6f7566]">
              {isCore ? CORE_SUMMARY.role : agent?.role}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close detail"
            className="rounded-md p-1 text-[#8d9483] transition-colors hover:bg-[rgba(200,255,0,0.08)] hover:text-[#c8ff00]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {isCore ? (
          <>
            <p className="mt-3 text-[13px] leading-relaxed text-[#eef2e2]/85">
              {CORE_SUMMARY.blurb}
            </p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {CORE_SUMMARY.readouts.map((r) => (
                <div
                  key={r.label}
                  className="rounded-lg border border-[rgba(200,255,0,0.12)] bg-[rgba(11,13,9,0.6)] px-3 py-2"
                >
                  <div className="font-[family-name:var(--font-space-grotesk)] text-lg font-bold text-[#c8ff00]">
                    {r.value}
                  </div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[#6f7566]">
                    {r.label}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : agent ? (
          <>
            <p className="mt-3 text-[13px] font-medium leading-relaxed text-[#eef2e2]/90">
              {agent.blurb}
            </p>
            <p className="mt-2 text-[12px] leading-relaxed text-[#8d9483]">
              {agent.detail}
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}
