"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy, RefreshCw, User, Volume2, Wrench } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { MarkdownContent } from "@/components/chat/markdown-content";
import { formatFullTime } from "@/lib/utils/format";
import type { ChatMessage } from "@/lib/stores/chat-store";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Spinner } from "@/components/ui/spinner";
import { speakWav, stopAudio } from "@/lib/api/voice";

/** Progressively reveal assistant content so single-chunk streams feel live. */
function useReveal(content: string, animate: boolean): string {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!animate || tick >= content.length) return;
    const tickMs = 33;
    const perTick = Math.max(6, Math.ceil(content.length / 900));
    const id = window.setTimeout(() => {
      setTick((prev) => Math.min(content.length, prev + perTick));
    }, tickMs);
    return () => window.clearTimeout(id);
  }, [animate, tick, content.length]);

  return content.slice(0, animate ? tick : content.length);
}

function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        } catch {
          /* ignore */
        }
      }}
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground",
        className
      )}
      aria-label="Copy message"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// Synthesized audio URLs cached per message so replay doesn't re-run TTS.
const speakUrlCache = new Map<string, string>();

function SpeakButton({ message }: { message: ChatMessage }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const toggle = async () => {
    if (playing) {
      audioRef.current?.pause();
      audioRef.current = null;
      setPlaying(false);
      return;
    }
    stopAudio();
    try {
      let url = speakUrlCache.get(message.id);
      if (!url) {
        const blob = await speakWav(message.content);
        url = URL.createObjectURL(blob);
        speakUrlCache.set(message.id, url);
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      await audio.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => void toggle()}
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground"
          aria-label={playing ? "Stop speech" : "Speak message"}
        >
          <Volume2 className={cn("h-3.5 w-3.5", playing && "text-accent")} />
        </button>
      </TooltipTrigger>
      <TooltipContent>{playing ? "Stop" : "Speak"}</TooltipContent>
    </Tooltip>
  );
}

function ToolTrace({ message }: { message: ChatMessage }) {
  if (!message.toolCalls || message.toolCalls.length === 0) return null;
  return (
    <div className="mb-3 space-y-1.5">
      {message.toolCalls.map((call, i) => {
        const running = call.result === undefined;
        return (
          <div
            key={i}
            className={cn(
              "rounded-lg border bg-card/90 px-3 py-2 backdrop-blur-sm",
              running
                ? "glow-border border-cyan-300/20"
                : "glow-border-gold border-amber-400/20"
            )}
            title={call.result !== undefined ? JSON.stringify(call.result) : "running…"}
          >
            <div className="flex items-center gap-2">
              {running ? (
                <Spinner className="h-3.5 w-3.5 text-accent" />
              ) : (
                <Wrench className="h-3.5 w-3.5 text-amber-300" />
              )}
              <span className="font-mono text-[11px] font-semibold text-cyan-100">
                {call.tool}
              </span>
              <span className="ml-auto rounded border border-border/60 px-1.5 py-px font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
                {running ? "executing" : "complete"}
              </span>
            </div>
            {call.result !== undefined && (
              <pre className="mt-1.5 max-h-24 overflow-auto rounded border border-border/40 bg-code-bg/80 p-2 font-mono text-[10px] leading-relaxed text-muted-foreground">
                {typeof call.result === "string"
                  ? call.result
                  : JSON.stringify(call.result, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Message({
  message,
  isStreaming,
  canRegenerate,
  onRegenerate,
}: {
  message: ChatMessage;
  isStreaming: boolean;
  canRegenerate: boolean;
  onRegenerate: () => void;
}) {
  const animate = message.role === "assistant" && isStreaming;
  const revealed = useReveal(message.content, animate);
  const showCursor = isStreaming && message.role === "assistant";

  if (message.role === "user") {
    return (
      <div className="flex justify-end px-4 py-3">
        <div className="group flex max-w-[78%] items-start gap-2">
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
                {formatFullTime(message.createdAt)}
              </span>
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-accent/15 text-accent">
                <User className="h-3.5 w-3.5" />
              </span>
            </div>
            <div className="rounded-2xl rounded-tr-sm border border-accent/25 bg-accent-subtle px-4 py-2.5 text-[14px] leading-relaxed text-foreground whitespace-pre-wrap">
              {message.content}
            </div>
            <div className="flex h-6 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
              <CopyButton text={message.content} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (message.role === "system") {
    return (
      <div className="px-4 py-2">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-[12px] text-muted-foreground">
          <span className="font-mono text-[10px] uppercase tracking-wider">system</span>
          <span className="flex-1 whitespace-pre-wrap">{message.content}</span>
        </div>
      </div>
    );
  }

  // assistant (default) + tool
  return (
    <div className="group/msg px-4 py-3">
      <div className="mx-auto flex max-w-3xl items-start gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent/25 to-accent/10 font-mono text-[11px] font-bold text-accent ring-1 ring-accent/30">
          x
        </div>

        <div className="min-w-0 flex-1">
          <ToolTrace message={message} />

          {message.status === "error" && !message.content ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-[13px] text-red-300">
              {message.error || "Generation failed"}
            </div>
          ) : (
            <div className="flex items-start gap-1">
              <div className="min-w-0 flex-1">
                <MarkdownContent content={revealed} />
                {showCursor && <span className="streaming-cursor" />}
                {message.status === "error" && message.content && (
                  <div className="mt-2 text-[12px] text-red-400">
                    {message.error}
                  </div>
                )}
              </div>
            </div>
          )}

          {!isStreaming && message.content && (
            <div className="mt-1 flex h-6 items-center gap-0.5 opacity-0 transition-opacity group-hover/msg:opacity-100">
              <CopyButton text={message.content} />
              {message.role === "assistant" && <SpeakButton message={message} />}
              {canRegenerate && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={onRegenerate}
                      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground"
                      aria-label="Regenerate response"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>Regenerate</TooltipContent>
                </Tooltip>
              )}
              <span className="pl-1 font-mono text-[10px] text-muted-foreground/50">
                {message.modelUsed || "ornith"} · {formatFullTime(message.createdAt)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
