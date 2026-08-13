"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AGENTS, CORE_ID } from "@/lib/constellation/data";
import { CoreOrb } from "./core-orb";
import { AgentOrb } from "./agent-orb";

export type StageSelection = string | null;

type ConstellationStageProps = {
  selected: StageSelection;
  onSelect: (id: string) => void;
  onClear: () => void;
};

/** Generate a deterministic starfield for the backdrop. */
function starfield(seed: number, count: number) {
  const stars: { x: number; y: number; r: number; delay: number }[] = [];
  let s = seed;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
  for (let i = 0; i < count; i++) {
    stars.push({
      x: rand(),
      y: rand(),
      r: 0.6 + rand() * 1.4,
      delay: rand() * 4,
    });
  }
  return stars;
}

export function ConstellationStage({ selected, onSelect, onClear }: ConstellationStageProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: r.width, h: r.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Core anchor — deliberately off-center so the field reads as a
  // constellation, not a hub-and-spoke diagram.
  const core = useMemo(() => ({ x: 0.44 * size.w, y: 0.47 * size.h }), [size.w, size.h]);

  const nodePos = useMemo(
    () =>
      new Map(
        AGENTS.map((a) => [
          a.id,
          { x: a.pos.x * size.w, y: a.pos.y * size.h, r: (a.weight * 92) / 2 },
        ])
      ),
    [size.w, size.h]
  );

  // Curved orbital links (quadratic, control offset perpendicular to the
  // chord) so connections read as arcs, not straight spokes.
  const linkPath = useCallback(
    (id: string) => {
      const n = nodePos.get(id);
      if (!n) return "";
      const dx = n.x - core.x;
      const dy = n.y - core.y;
      const dist = Math.hypot(dx, dy);
      const bend = Math.min(0.28 * dist, 90);
      const mx = (core.x + n.x) / 2;
      const my = (core.y + n.y) / 2;
      const nx = -dy / dist;
      const ny = dx / dist;
      const cx = mx + nx * bend;
      const cy = my + ny * bend;
      return `M ${core.x} ${core.y} Q ${cx} ${cy} ${n.x} ${n.y}`;
    },
    [core.x, core.y, nodePos]
  );

  const stars = useMemo(() => starfield(20260813, 90), []);

  const isSelected = (id: string) => selected === id;
  const coreSelected = selected === CORE_ID;
  const anySelected = selected != null;

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        onClear();
        return;
      }
      if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const order = [CORE_ID, ...AGENTS.map((a) => a.id)];
        const current = selected ?? CORE_ID;
        const idx = order.indexOf(current);
        const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
        const next = order[(idx + dir + order.length) % order.length];
        onSelect(next);
      }
    },
    [selected, onSelect, onClear]
  );

  return (
    <div
      ref={wrapRef}
      className="relative h-full w-full select-none overflow-hidden"
      onKeyDown={onKeyDown}
      onClick={() => anySelected && onClear()}
      role="group"
      aria-label="xnchSystems agent constellation. Use arrow keys to move focus, Enter to select."
    >
      {/* Starfield */}
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        {stars.map((s, i) => (
          <span
            key={i}
            className="const-star absolute rounded-full bg-[#c8ff00]"
            style={{
              left: `${s.x * 100}%`,
              top: `${s.y * 100}%`,
              width: s.r,
              height: s.r,
              animationDelay: `${s.delay}s`,
              opacity: 0.2,
            }}
          />
        ))}
      </div>

      {/* Orbital links */}
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
      >
        {size.w > 0 &&
          AGENTS.map((a) => {
            const active =
              isSelected(a.id) || (coreSelected && a.status.state !== "standby");
            const dimmed = anySelected && !isSelected(a.id) && !coreSelected;
            return (
              <g key={a.id} opacity={dimmed ? 0.22 : 1} style={{ transition: "opacity 300ms" }}>
                <path
                  d={linkPath(a.id)}
                  fill="none"
                  stroke="rgba(200,255,0,0.4)"
                  strokeWidth={active ? 2.4 : 1.2}
                  opacity={active ? 0.9 : 0.45}
                  strokeLinecap="round"
                />
                {active && (
                  <path
                    className="const-link-active"
                    d={linkPath(a.id)}
                    fill="none"
                    stroke="rgba(200,255,0,0.85)"
                    strokeWidth={1.6}
                    strokeLinecap="round"
                  />
                )}
              </g>
            );
          })}
      </svg>

      {/* Nodes */}
      <div className="absolute inset-0">
        {size.w > 0 && (
          <div
            className="absolute"
            style={{ left: core.x, top: core.y, transform: "translate(-50%, -50%)" }}
          >
            <CoreOrb
              size={132}
              selected={coreSelected}
              onSelect={() => onSelect(CORE_ID)}
            />
          </div>
        )}

        {size.w > 0 &&
          AGENTS.map((a) => {
          const pos = nodePos.get(a.id)!;
          return (
            <div
              key={a.id}
              className="absolute"
              style={{
                left: pos.x,
                top: pos.y,
                transform: "translate(-50%, -50%)",
                zIndex: isSelected(a.id) ? 20 : 10,
                visibility: size.w > 0 ? "visible" : "hidden",
              }}
            >
              <AgentOrb
                agent={a}
                selected={isSelected(a.id)}
                dimmed={anySelected && !isSelected(a.id) && !coreSelected}
                onSelect={() => onSelect(a.id)}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
