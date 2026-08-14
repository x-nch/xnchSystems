"use client";

import { useEffect, useRef } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageList } from "@/components/chat/message-list";
import { Badge } from "@/components/ui/badge";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { playText } from "@/lib/api/voice";
import { cn } from "@/lib/utils/cn";

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
  const voiceAutoSpeak = useSettingsStore((s) => s.voiceAutoSpeak);
  const setVoiceAutoSpeak = useSettingsStore((s) => s.setVoiceAutoSpeak);

  const conversation = conversations.find((c) => c.id === activeConversationId);
  const streaming = streamingConversationId === conversation?.id;
  const spokenRef = useRef<Set<string>>(new Set());

  const handleSend = (text: string) => {
    void sendMessage(text);
  };

  // Auto-speak the latest assistant reply once it finishes streaming (toggle).
  useEffect(() => {
    if (!voiceAutoSpeak || streaming) return;
    const last = conversation?.messages[conversation.messages.length - 1];
    if (!last || last.role !== "assistant" || last.status !== "done") return;
    const content = (last.content ?? "").trim();
    if (!content || spokenRef.current.has(last.id)) return;
    spokenRef.current.add(last.id);
    playText(content).catch(() => {
      /* TTS unavailable — silence */
    });
  }, [conversation, streaming, voiceAutoSpeak]);

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-8 shrink-0 items-center gap-2 border-b border-border/80 bg-card/30 px-4 backdrop-blur-sm">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-200/80">
          Session
        </span>
        <span className="text-xs font-medium text-foreground">
          {conversation?.title ?? "New session"}
        </span>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => setVoiceAutoSpeak(!voiceAutoSpeak)}
          aria-pressed={voiceAutoSpeak}
          aria-label={voiceAutoSpeak ? "Disable auto-speak" : "Enable auto-speak"}
          className={cn(
            "inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors",
            voiceAutoSpeak
              ? "text-accent hover:bg-muted"
              : "text-muted-foreground/60 hover:bg-muted hover:text-foreground"
          )}
          title={voiceAutoSpeak ? "Auto-speak on" : "Auto-speak off"}
        >
          {voiceAutoSpeak ? (
            <Volume2 className="h-3.5 w-3.5" />
          ) : (
            <VolumeX className="h-3.5 w-3.5" />
          )}
        </button>
        {conversation && (
          <Badge tone="muted" className="font-mono">
            {conversation.id.slice(0, 8)}
          </Badge>
        )}
        <Badge tone="muted" className="font-mono">
          role:{actorRole}
        </Badge>
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
