"use client";

import { ChatInput } from "@/components/chat/chat-input";
import { LlmStatus } from "@/components/chat/llm-status";
import { MessageList } from "@/components/chat/message-list";
import { Badge } from "@/components/ui/badge";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function ChatView() {
  const {
    conversations,
    activeConversationId,
    streamingConversationId,
    sendMessage,
    stopStreaming,
    regenerateLast,
  } = useChatStore();
  const actorRole = useSettingsStore((s) => s.actorRole);

  const conversation = conversations.find((c) => c.id === activeConversationId);
  const streaming = streamingConversationId === conversation?.id;

  const handleSend = (text: string) => {
    void sendMessage(text);
  };

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-8 shrink-0 items-center gap-2 border-b border-border/80 bg-card/30 px-4 backdrop-blur-sm">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          Session
        </span>
        <span className="text-xs font-medium text-foreground">
          {conversation?.title ?? "New session"}
        </span>
        <span className="flex-1" />
        {conversation && (
          <Badge tone="muted" className="font-mono">
            {conversation.id.slice(0, 8)}
          </Badge>
        )}
        <Badge tone="muted" className="font-mono">
          role:{actorRole}
        </Badge>
        <LlmStatus />
      </div>

      <div className="min-h-0 flex-1">
        {conversation ? (
          <MessageList
            conversation={conversation}
            isStreaming={streaming}
            onRegenerate={() => void regenerateLast()}
          />
        ) : (
          <MessageList
            conversation={{
              id: "empty",
              title: "",
              createdAt: 0,
              updatedAt: 0,
              messages: [],
            }}
            isStreaming={false}
            onRegenerate={() => {}}
          />
        )}
      </div>

      <ChatInput
        disabled={false}
        streaming={streaming}
        onSend={handleSend}
        onStop={stopStreaming}
      />
    </div>
  );
}
