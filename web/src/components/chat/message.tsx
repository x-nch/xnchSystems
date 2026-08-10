"use client";

import { useEffect, useState } from "react";
import { Check, Copy, RefreshCw, User } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { MarkdownContent } from "@/components/chat/markdown-content";
import { formatFullTime } from "@/lib/utils/format";
import type { ChatMessage } from "@/lib/stores/chat-store";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

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

function ToolTrace({ message }: { message: ChatMessage }) {
  if (!message.toolCalls || message.toolCalls.length === 0) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {message.toolCalls.map((call, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
          title={call.result !== undefined ? JSON.stringify(call.result) : "running…"}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent/70" />
          {call.tool}
        </span>
      ))}
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
