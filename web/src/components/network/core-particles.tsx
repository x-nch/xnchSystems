"use client";

import { useEffect, useRef } from "react";

/** Tiny orbiting particle field inside the core node. */
export function CoreParticles() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = 104;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const particles = Array.from({ length: 48 }, (_, i) => ({
      angle: (i / 48) * Math.PI * 2,
      radius: 18 + Math.random() * 28,
      speed: 0.004 + Math.random() * 0.008,
      size: 0.6 + Math.random() * 1.2,
      hue: Math.random() > 0.75 ? "gold" : "cyan",
    }));

    let raf = 0;
    const cx = size / 2;
    const cy = size / 2;

    const frame = () => {
      ctx.clearRect(0, 0, size, size);
      ctx.globalCompositeOperation = "lighter";

      for (const p of particles) {
        p.angle += p.speed;
        const x = cx + Math.cos(p.angle) * p.radius;
        const y = cy + Math.sin(p.angle) * p.radius;
        const dist = Math.hypot(x - cx, y - cy);
        const alpha = Math.max(0.15, 1 - dist / (size * 0.48));

        ctx.globalAlpha = alpha * 0.85;
        ctx.fillStyle = p.hue === "gold" ? "#f5c518" : "#22d3ee";
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // circuit ring
      ctx.globalAlpha = 0.22;
      ctx.strokeStyle = "#22d3ee";
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
      aria-hidden
    />
  );
}
