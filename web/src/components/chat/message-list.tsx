"use client";

import { useEffect, useRef } from "react";
import { Message } from "@/components/chat/message";
import type { Conversation } from "@/lib/stores/chat-store";

export function MessageList({
  conversation,
  isStreaming,
  onRegenerate,
}: {
  conversation: Conversation;
  isStreaming: boolean;
  onRegenerate: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const contentKey = conversation.messages
    .map((m) => `${m.id}:${m.content.length}:${m.status}`)
    .join("|");

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [contentKey, conversation.id]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottom.current = distance < 120;
  };

  const lastUserIndex = [...conversation.messages]
    .reverse()
    .findIndex((m) => m.role === "user");
  const lastUserIdx =
    lastUserIndex === -1
      ? -1
      : conversation.messages.length - 1 - lastUserIndex;

  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      className="h-full overflow-y-auto overscroll-contain"
    >
      <div className="min-h-full">
        {conversation.messages.length === 0 ? (
          <div className="flex min-h-full items-center justify-center">
            <EmptyChat />
          </div>
        ) : (
          conversation.messages.map((message, i) => (
            <Message
              key={message.id}
              message={message}
              isStreaming={isStreaming && i === conversation.messages.length - 1}
              canRegenerate={
                message.role === "assistant" &&
                i === conversation.messages.length - 1 &&
                i > lastUserIdx &&
                lastUserIdx !== -1 &&
                !isStreaming
              }
              onRegenerate={onRegenerate}
            />
          ))
        )}
      </div>
    </div>
  );
}

function EmptyChat() {
  const suggestions = [
    "What can you do on this system?",
    "Summarize my recent context and open threads.",
    "Check the health of the node-a services.",
    "Explain the memory recall pipeline.",
  ];
  return (
    <div className="max-w-md px-6 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-accent/25 to-accent/5 font-mono text-xl font-bold text-accent ring-1 ring-accent/30">
        x
      </div>
      <h2 className="text-lg font-semibold tracking-tight">
        xnch control surface
      </h2>
      <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
        A governed conversation with your private AI orchestration stack —
        memory, MCP tools, policy and learning all routed through the gateway.
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {suggestions.map((s) => (
          <span
            key={s}
            className="rounded-full border border-border bg-muted/40 px-3 py-1 text-[11px] text-muted-foreground transition-colors hover:border-accent/40 hover:text-foreground"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}
