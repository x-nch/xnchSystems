"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Mic, Square } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { transcribeWav } from "@/lib/api/voice";
import { VoiceRecorder } from "@/lib/voice/recorder";

const HOLD_MS = 250;

type VoiceState = "idle" | "recording" | "transcribing";

export function VoiceButton({
  disabled,
  onTranscript,
  onError,
}: {
  disabled?: boolean;
  onTranscript: (text: string) => void;
  onError?: (message: string) => void;
}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const downAtRef = useRef(0);
  const toggledRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  const ticker = () => {
    const rec = recorderRef.current;
    if (!rec) return;
    setElapsed(rec.durationMs);
    timerRef.current = window.setTimeout(ticker, 100);
  };

  const finish = async (cancel: boolean) => {
    if (timerRef.current != null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    setElapsed(0);
    setLevel(0);
    const rec = recorderRef.current;
    recorderRef.current = null;
    toggledRef.current = false;
    if (!rec) return;
    if (cancel) {
      rec.cancel();
      setState("idle");
      return;
    }
    setState("transcribing");
    try {
      const wav = await rec.stop();
      const result = await transcribeWav(wav);
      const text = (result.transcript ?? "").trim();
      if (text) onTranscript(text);
      else onError?.("Couldn't hear anything — try again.");
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Voice transcription failed");
    } finally {
      setState("idle");
    }
  };

  const onPointerDown = async (e: React.PointerEvent) => {
    if (disabled || state === "transcribing") return;
    // In toggle mode: this tap stops recording.
    if (state === "recording" && toggledRef.current) {
      void finish(false);
      return;
    }
    if (state !== "idle") return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    downAtRef.current = Date.now();
    toggledRef.current = false;
    try {
      const rec = new VoiceRecorder({
        onLevel: (rms) => setLevel(Math.min(1, rms * 4)),
        onTimeout: () => void finish(false),
      });
      await rec.start();
      recorderRef.current = rec;
      setState("recording");
      setElapsed(0);
      timerRef.current = window.setTimeout(ticker, 100);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Microphone unavailable");
    }
  };

  const onPointerUp = () => {
    if (state !== "recording" || toggledRef.current) return;
    const held = Date.now() - downAtRef.current;
    if (held >= HOLD_MS) {
      void finish(false); // hold-to-talk
    } else {
      toggledRef.current = true; // quick tap -> toggle mode; next tap stops
    }
  };

  const onPointerCancel = () => {
    if (state === "recording") void finish(true);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
      recorderRef.current?.cancel();
    };
  }, []);

  const recording = state === "recording";

  return (
    <button
      type="button"
      aria-label={recording ? "Stop recording" : "Record voice"}
      aria-pressed={recording}
      disabled={disabled || state === "transcribing"}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
      className={cn(
        "relative inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-colors",
        state === "idle" && "border-border bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
        recording && "border-red-500/40 bg-red-500/10 text-red-400",
        state === "transcribing" && "border-border bg-muted text-muted-foreground",
        disabled && "pointer-events-none opacity-40"
      )}
    >
      {state === "transcribing" ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : recording ? (
        <Square className="h-3.5 w-3.5" />
      ) : (
        <Mic className="h-4 w-4" />
      )}
      {recording && (
        <span
          className="absolute inset-0 rounded-lg ring-2 ring-red-500/50"
          style={{
            animation: "voice-pulse 1.2s ease-out infinite",
          }}
        />
      )}
      {recording && (
        <span className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 font-mono text-[9px] text-red-400">
          {(elapsed / 1000).toFixed(1)}s
        </span>
      )}
      {recording && level > 0.1 && (
        <span
          className="absolute inset-0 rounded-lg border border-red-400/20"
          style={{ transform: `scale(${1 + level * 0.12})` }}
        />
      )}
    </button>
  );
}
