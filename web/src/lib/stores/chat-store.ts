"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { streamChatEvents } from "@/lib/api/client";
import { useSettingsStore } from "@/lib/stores/settings-store";

export type MessageRole = "user" | "assistant" | "system" | "tool";
export type MessageStatus = "streaming" | "done" | "error";

export interface ToolCallTrace {
  tool: string;
  arguments: unknown;
  result?: unknown;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  error?: string;
  modelUsed?: string;
  toolCalls?: ToolCallTrace[];
  createdAt: number;
}

export interface Conversation {
  /** session_id sent to the gateway. */
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

const uid = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

// Abort controllers live outside the store so streaming can be cancelled from
// anywhere without persisting transient state.
const activeStreams = new Map<string, AbortController>();

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  streamingConversationId: string | null;

  createConversation: () => string;
  deleteConversation: (id: string) => void;
  selectConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  sendMessage: (text: string) => Promise<void>;
  regenerateLast: () => Promise<void>;
  stopStreaming: () => void;
  isStreaming: (conversationId: string) => boolean;
}

function deriveTitle(text: string): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!clean) return "New chat";
  return clean.length > 48 ? `${clean.slice(0, 48)}…` : clean;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      streamingConversationId: null,

      createConversation: () => {
        const id = uid();
        const conversation: Conversation = {
          id,
          title: "New chat",
          createdAt: Date.now(),
          updatedAt: Date.now(),
          messages: [],
        };
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          activeConversationId: id,
        }));
        return id;
      },

      deleteConversation: (id) => {
        activeStreams.get(id)?.abort();
        activeStreams.delete(id);
        set((state) => {
          const conversations = state.conversations.filter((c) => c.id !== id);
          const activeConversationId =
            state.activeConversationId === id
              ? (conversations[0]?.id ?? null)
              : state.activeConversationId;
          return {
            conversations,
            activeConversationId,
            streamingConversationId:
              state.streamingConversationId === id
                ? null
                : state.streamingConversationId,
          };
        });
      },

      selectConversation: (id) => set({ activeConversationId: id }),

      renameConversation: (id, title) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title } : c
          ),
        })),

      sendMessage: async (text) => {
        const state = get();
        let conversationId = state.activeConversationId;
        if (!conversationId) conversationId = get().createConversation();

        const actorRole = useSettingsStore.getState().actorRole || "operator";
        const now = Date.now();

        const userMessage: ChatMessage = {
          id: uid(),
          role: "user",
          content: text,
          status: "done",
          createdAt: now,
        };
        const assistantMessage: ChatMessage = {
          id: uid(),
          role: "assistant",
          content: "",
          status: "streaming",
          createdAt: now,
        };

        set((s) => ({
          conversations: s.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            const messages = [...c.messages, userMessage, assistantMessage];
            return {
              ...c,
              messages,
              updatedAt: now,
              title:
                c.title === "New chat" ? deriveTitle(text) : c.title,
            };
          }),
          streamingConversationId: conversationId,
        }));

        const controller = new AbortController();
        activeStreams.set(conversationId, controller);

        const setAssistant = (updater: (m: ChatMessage) => ChatMessage) =>
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === conversationId
                ? {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === assistantMessage.id ? updater(m) : m
                    ),
                  }
                : c
            ),
          }));

        try {
          await streamChatEvents(
            {
              session_id: conversationId,
              message: text,
              actor_role: actorRole,
            },
            {
              signal: controller.signal,
              onEvent: (event) => {
                switch (event.type) {
                  case "content":
                    setAssistant((m) => ({ ...m, content: event.content }));
                    break;
                  case "delta":
                    setAssistant((m) => ({ ...m, content: m.content + event.delta }));
                    break;
                  case "tool_call":
                    setAssistant((m) => ({
                      ...m,
                      toolCalls: [
                        ...(m.toolCalls ?? []),
                        { tool: event.tool, arguments: event.arguments },
                      ],
                    }));
                    break;
                  case "tool_result":
                    setAssistant((m) => {
                      const toolCalls = [...(m.toolCalls ?? [])];
                      const last = toolCalls.findIndex(
                        (t) => t.tool === event.tool && t.result === undefined
                      );
                      if (last !== -1) toolCalls[last] = { ...toolCalls[last], result: event.result };
                      return { ...m, toolCalls };
                    });
                    break;
                  case "error":
                    setAssistant((m) => ({
                      ...m,
                      status: "error",
                      error: event.message,
                    }));
                    break;
                  case "done":
                    setAssistant((m) => ({
                      ...m,
                      status: m.status === "error" ? "error" : "done",
                    }));
                    break;
                  case "meta":
                    break;
                }
              },
            }
          );
        } finally {
          activeStreams.delete(conversationId);
          set((s) => ({
            streamingConversationId:
              s.streamingConversationId === conversationId
                ? null
                : s.streamingConversationId,
          }));
        }
      },

      regenerateLast: async () => {
        const state = get();
        const conversation = state.conversations.find(
          (c) => c.id === state.activeConversationId
        );
        if (!conversation || state.streamingConversationId) return;

        const lastUserIdx = [...conversation.messages]
          .reverse()
          .findIndex((m) => m.role === "user");
        if (lastUserIdx === -1) return;
        const userIndex = conversation.messages.length - 1 - lastUserIdx;
        const userMessage = conversation.messages[userIndex];

        // Drop everything after the last user turn, then re-run it.
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === conversation.id
              ? { ...c, messages: c.messages.slice(0, userIndex + 1) }
              : c
          ),
        }));
        await get().sendMessage(userMessage.content);
      },

      stopStreaming: () => {
        const streamingId = get().streamingConversationId;
        if (!streamingId) return;
        const controller = activeStreams.get(streamingId);
        controller?.abort();
        activeStreams.delete(streamingId);
      },

      isStreaming: (conversationId) =>
        get().streamingConversationId === conversationId,
    }),
    {
      name: "xnch-ui-chat",
      partialize: (state) => ({
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
      }),
    }
  )
);
