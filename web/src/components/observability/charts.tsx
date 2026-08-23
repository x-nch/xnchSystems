"use client";

import * as React from "react";
import { cn } from "@/lib/utils/cn";

/**
 * Dependency-free SVG chart primitives for the observability screens.
 *
 * Design constraints (standing UI requirements):
 * - chartreuse accent used functionally (data ink), not decoratively
 * - static strokes / no animation => respects prefers-reduced-motion by default
 * - AA contrast: grid/axis use muted tokens, data uses --accent on --background
 */

interface Point {
  x: number;
  y: number;
}

export function toPoints(points: [number, number][], w: number, h: number, pad: number): Point[] {
  if (points.length === 0) return [];
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...ys, 1e-9);
  const minY = Math.min(0, ...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const iw = w - pad * 2;
  const ih = h - pad * 2;
  return points.map(([t, v]) => ({
    x: pad + ((t - minX) / spanX) * iw,
    y: pad + ih - ((v - minY) / spanY) * ih,
  }));
}

export function linePath(pts: Point[]): string {
  return pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
}

export interface LineChartProps extends React.SVGAttributes<SVGSVGElement> {
  series: [number, number][];
  height?: number;
  label?: string;
  unit?: string;
  /** Optional reference line (e.g. VRAM budget ceiling), same units as data. */
  threshold?: number;
  ariaLabel: string;
}

export function LineChart({
  series,
  height = 96,
  label,
  unit,
  threshold,
  ariaLabel,
  className,
  ...props
}: LineChartProps) {
  const W = 320;
  const H = height;
  const PAD = 6;

  if (series.length < 2) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-md border border-border text-[11px] text-muted-foreground",
          className
        )}
        style={{ height: `${H}px` }}
        role="img"
        aria-label={`${ariaLabel} — insufficient data`}
      >
        no data yet
      </div>
    );
  }

  // Shared domain across data AND threshold so both render in one coordinate space.
  const xs = series.map((p) => p[0]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...series.map((p) => p[1]), threshold ?? 0, 1e-9);

  const iw = W - PAD * 2;
  const ih = H - PAD * 2;
  const spanX = maxX - minX || 1;

  const scaleX = (t: number) => PAD + ((t - minX) / spanX) * iw;
  const scaleY = (v: number) => PAD + ih - (v / maxY) * ih; // domain is 0..maxY

  const pts = series.map(([t, v]) => ({ x: scaleX(t), y: scaleY(v) }));
  const last = series[series.length - 1];
  const thrY = threshold != null ? scaleY(threshold) : null;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={cn("w-full", className)}
      role="img"
      aria-label={ariaLabel}
      preserveAspectRatio="none"
      {...props}
    >
      {thrY != null && (
        <line
          x1={PAD}
          y1={thrY}
          x2={W - PAD}
          y2={thrY}
          stroke="var(--state-attention, #FFB000)"
          strokeWidth="1"
          strokeDasharray="4 3"
        />
      )}
      <path
        d={linePath(pts)}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <title>
        {`${label ?? ariaLabel}: latest ${last[1].toFixed(1)}${unit ?? ""}`}
      </title>
    </svg>
  );
}

export interface BarChartProps {
  bars: { label: string; value: number }[];
  height?: number;
  ariaLabel: string;
  className?: string;
}

export function BarChart({ bars, height = 96, ariaLabel, className }: BarChartProps) {
  const maxV = Math.max(...bars.map((b) => b.value), 1e-9);
  return (
    <div
      className={cn("flex items-end gap-3", className)}
      style={{ minHeight: height }}
      role="img"
      aria-label={ariaLabel}
    >
      {bars.map((b) => (
        <div key={b.label} className="flex flex-1 flex-col items-center gap-1">
          <span className="font-mono text-[11px] text-muted-foreground">
            {Number.isFinite(b.value) ? b.value.toLocaleString() : "—"}
          </span>
          <div
            className={cn(
              "w-full rounded-t-sm",
              b.value > 0 ? "bg-[var(--accent)]" : "border border-border bg-transparent"
            )}
            style={{ height: `${Math.max((b.value / maxV) * (height - 28), b.value > 0 ? 4 : 2)}px` }}
          />
          <span className="text-[11px] text-muted-foreground">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Cumulative-histogram bars for time-to-decision distributions. */
export function TtdHistogram({
  buckets,
  height = 110,
}: {
  buckets: { le: string; count: number }[];
  height?: number;
}) {
  const finite = buckets.filter((b) => b.le !== "+Inf");
  const inf = buckets.find((b) => b.le === "+Inf");
  if (finite.length === 0 && !inf) {
    return <p className="text-[12px] text-muted-foreground">No decisions recorded yet.</p>;
  }
  const rows = [
    ...finite.map((b) => ({ label: `≤${b.le}s`, value: b.count })),
    ...(inf ? [{ label: "total", value: inf.count }] : []),
  ];
  return <BarChart bars={rows} height={height} ariaLabel="Time-to-decision distribution" />;
}
