"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";

const MAX_ROWS = 8;

export function ChatInput({
  disabled,
  streaming,
  onSend,
  onStop,
}: {
  disabled: boolean;
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_ROWS * 22)}px`;
  }, [value]);

  // Keep focus after streaming finishes so the user can type the next prompt.
  useEffect(() => {
    if (!streaming) textareaRef.current?.focus();
  }, [streaming]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled || streaming) return;
    setValue("");
    onSend(text);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    } else if (e.key === "Escape" && streaming) {
      e.preventDefault();
      onStop();
    }
  };

  return (
    <div className="shrink-0 border-t border-border bg-background/70 px-4 pb-3 pt-2 backdrop-blur supports-[backdrop-filter]:bg-background/50">
      {streaming && (
        <div className="mx-auto mb-2 flex max-w-3xl items-center gap-2 text-[11px] text-muted-foreground">
          <span className="flex gap-0.5">
            <span className="streaming-dot h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="streaming-dot h-1.5 w-1.5 rounded-full bg-accent [animation-delay:150ms]" />
            <span className="streaming-dot h-1.5 w-1.5 rounded-full bg-accent [animation-delay:300ms]" />
          </span>
          Generating response…
          <span className="flex-1" />
          <Kbd>esc</Kbd>
          <span className="text-muted-foreground/70">stop</span>
        </div>
      )}

      <div className="mx-auto max-w-3xl">
        <div
          className={cn(
            "flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm transition-colors",
            "focus-within:border-accent/50 focus-within:ring-2 focus-within:ring-ring/25"
          )}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Message the control plane…"
            disabled={disabled}
            className="max-h-44 flex-1 resize-none bg-transparent px-2 py-1.5 text-[14px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/60 disabled:opacity-60"
          />
          {streaming ? (
            <Button
              size="icon"
              variant="destructive"
              onClick={onStop}
              className="shrink-0"
              aria-label="Stop generation"
            >
              <Square className="h-4 w-4" fill="currentColor" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={submit}
              disabled={!value.trim() || disabled}
              className="shrink-0"
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="mt-1.5 flex items-center gap-1 px-2 text-[10px] text-muted-foreground/60">
          <span className="inline-flex items-center gap-1">
            <Kbd>Enter</Kbd> send
          </span>
          <span className="mx-1.5 h-3 w-px bg-border" />
          <span className="inline-flex items-center gap-1">
            <Kbd>Shift</Kbd>
            <Kbd>Enter</Kbd> newline
          </span>
          <span className="flex-1" />
          <span>routed via xnch :8001</span>
        </div>
      </div>
    </div>
  );
}
