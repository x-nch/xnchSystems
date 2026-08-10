"use client";

import { useEffect, useRef } from "react";

type Particle = {
  tx: number;
  ty: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  phase: number;
  k: number;
};

/** Rasterize a normalized humanoid silhouette and return mask points in [0,1]². */
function buildMaskPoints(): Array<[number, number]> {
  const W = 200;
  const H = 300;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d");
  if (!g) return [];
  g.clearRect(0, 0, W, H);
  g.fillStyle = "#fff";
  g.beginPath();
  g.ellipse(100, 62, 40, 48, 0, 0, Math.PI * 2);
  g.fill();
  g.fillRect(94, 106, 12, 20);
  g.beginPath();
  g.moveTo(32, 126);
  g.lineTo(168, 126);
  g.lineTo(124, 232);
  g.lineTo(76, 232);
  g.closePath();
  g.fill();
  g.beginPath();
  g.ellipse(24, 150, 12, 44, 0.06, 0, Math.PI * 2);
  g.fill();
  g.beginPath();
  g.ellipse(176, 150, 12, 44, -0.06, 0, Math.PI * 2);
  g.fill();
  const data = g.getImageData(0, 0, W, H).data;
  const points: Array<[number, number]> = [];
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (data[(y * W + x) * 4 + 3] > 128) {
        points.push([x / W, y / H]);
      }
    }
  }
  return points;
}

export function ParticleHumanoid({
  particleCount = 1400,
}: {
  particleCount?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const points = buildMaskPoints();
    if (points.length === 0) return;

    let width = 0;
    let height = 0;
    let raf = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const particles: Particle[] = Array.from({ length: particleCount }, () => {
      const [tx, ty] = points[Math.floor(Math.random() * points.length)];
      return {
        tx,
        ty,
        x: Math.random() * width,
        y: Math.random() * height,
        vx: 0,
        vy: 0,
        phase: Math.random() * Math.PI * 2,
        k: 0.012 + Math.random() * 0.01,
      };
    });

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let t = 0;
    let shed = 0;

    const frame = () => {
      t += 1;
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter";

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const tx = p.tx * width;
        const ty = p.ty * height;
        const dx = tx - p.x;
        const dy = ty - p.y;

        p.vx += dx * p.k + Math.sin(p.y * 0.004 + t * 0.6 + p.phase) * 0.5;
        p.vy += dy * p.k + Math.cos(p.x * 0.004 + t * 0.5 + p.phase * 1.7) * 0.5;
        p.vx *= 0.86;
        p.vy *= 0.86;
        p.x += p.vx;
        p.y += p.vy;

        const d = Math.sqrt(dx * dx + dy * dy);
        const a = Math.max(0, 1 - d / 130);

        // core glow — amber near center, cyan at edges
        const cx = width * 0.5;
        const cy = height * 0.38;
        const coreDist = Math.hypot(p.x - cx, p.y - cy);
        const isCore = coreDist < 55;
        const isMid = coreDist < 110;

        ctx.globalAlpha = 0.08 + a * 0.75;
        if (isCore) {
          ctx.fillStyle = i % 3 === 0 ? "#fbbf24" : "#f5c518";
        } else if (isMid) {
          ctx.fillStyle = i % 4 === 0 ? "#7dd3fc" : "#22d3ee";
        } else {
          ctx.fillStyle = i % 5 === 0 ? "#7dd3fc" : "#22d3ee";
        }
        ctx.fillRect(p.x, p.y, isCore ? 2.2 : 1.8, isCore ? 2.2 : 1.8);
      }

      shed += particles.length * 0.0015;
      const sheds = Math.floor(shed);
      shed -= sheds;
      for (let i = 0; i < sheds; i++) {
        const p = particles[Math.floor(Math.random() * particles.length)];
        const [tx, ty] = points[Math.floor(Math.random() * points.length)];
        p.tx = tx;
        p.ty = ty;
      }

      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [particleCount]);

  return <canvas ref={canvasRef} className="h-full w-full" />;
}
