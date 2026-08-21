"use client";

import { useEffect, useRef } from "react";

export function Waveform({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    let raf = 0;
    let t = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = w * 2;
      canvas.height = h * 2;
      ctx.scale(2, 2);
    };
    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const frame = () => {
      t += 0.04;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = "rgba(34, 211, 238, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x < w; x++) {
        const y =
          h / 2 +
          Math.sin(x * 0.04 + t) * 4 +
          Math.sin(x * 0.09 + t * 1.3) * 2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      raf = requestAnimationFrame(frame);
    };

    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
