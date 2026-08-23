"use client";

import { useEffect, useRef } from "react";

/** Deprecated — orbiting particles are removed in dark-minimalist.
 *  Kept for reference; renders static ring and respects reduced-motion. */
export function CoreParticles() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = 104;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    // Reduced to 12 particles, muted neutral palette — but core-node no longer mounts this.
    const particles = Array.from({ length: 12 }, (_, i) => ({
      angle: (i / 12) * Math.PI * 2,
      radius: 22 + Math.random() * 18,
      speed: 0.002 + Math.random() * 0.004,
      size: 0.8 + Math.random() * 0.8,
    }));

    let raf = 0;
    const cx = size / 2;
    const cy = size / 2;

    const frame = () => {
      ctx.clearRect(0, 0, size, size);
      for (const p of particles) {
        p.angle += p.speed;
        const x = cx + Math.cos(p.angle) * p.radius;
        const y = cy + Math.sin(p.angle) * p.radius;
        ctx.fillStyle = "rgba(242,244,247,0.35)";
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.strokeStyle = "rgba(242,244,247,0.12)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.arc(cx, cy, 34, 0, Math.PI * 2);
      ctx.stroke();
      raf = requestAnimationFrame(frame);
    };

    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={104}
      height={104}
      className="pointer-events-none absolute inset-0 h-full w-full rounded-full"
      data-motion="decorative"
      aria-hidden
    />
  );
}
