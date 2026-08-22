"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  MessageSquare,
  Database,
  Wrench,
  Activity,
  Orbit,
  ScanFace,
  GitBranch,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useMemorySurface } from "@/lib/api/hooks";
import { formatRelativeTime } from "@/lib/utils/format";
import { ConnectionStatus } from "@/components/layout/connection-status";

const NAV = [
  { href: "/", label: "Network", icon: Orbit, altHref: "/network" },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/memory", label: "Memory", icon: Database },
  { href: "/graph", label: "Graph", icon: GitBranch },
  { href: "/tools", label: "Tools", icon: Wrench },
  { href: "/system", label: "System", icon: Activity },
  { href: "/presence", label: "Presence", icon: ScanFace },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  const setCollapsed = useSettingsStore((s) => s.setSidebarCollapsed);
  const {
    conversations,
    activeConversationId,
    selectConversation,
    createConversation,
    deleteConversation,
    streamingConversationId,
  } = useChatStore();
  const surface = useMemorySurface();

  const surfaceCount =
    surface.data && Array.isArray(surface.data)
      ? surface.data.filter((e) => e.priority >= 1).length
      : 0;

  const newChat = () => {
    const id = createConversation();
    router.push("/chat");
    selectConversation(id);
  };

  const goChat = () => router.push("/chat");

  return (
    <aside
      className={cn(
        "relative flex h-full shrink-0 flex-col border-r border-border/80 bg-card/40 backdrop-blur-sm transition-[width] duration-200",
        collapsed ? "w-[var(--hud-sidebar-collapsed)]" : "w-[var(--hud-sidebar-width)]"
      )}
    >
      {/* Brand row */}
      <div
        className={cn(
          "flex h-[var(--hud-topbar-height)] shrink-0 items-center gap-2 border-b border-border/80 px-3",
          collapsed && "justify-center px-0"
        )}
      >
        {!collapsed && (
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-accent/15 font-mono text-[13px] font-bold text-accent">
              x
            </div>
            <span className="font-mono text-sm font-semibold tracking-tight">
              xnch
            </span>
            <span className="rounded-sm bg-muted px-1 py-px text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
              control
            </span>
          </div>
        )}
        <div className="flex-1" />
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* New chat */}
      <div className={cn("p-2", collapsed && "px-1.5")}>
        {collapsed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="secondary" size="icon" className="w-full" onClick={newChat}>
                <Plus className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">New chat</TooltipContent>
          </Tooltip>
        ) : (
          <Button variant="secondary" className="w-full justify-start" onClick={newChat}>
            <Plus className="h-4 w-4" />
            New chat
          </Button>
        )}
      </div>

      {/* Nav */}
      <nav className={cn("space-y-0.5 px-2", collapsed && "px-1.5")}>
        {NAV.map(({ href, label, icon: Icon, altHref }) => {
          const active =
            pathname === href ||
            pathname.startsWith(`${href}/`) ||
            (altHref != null && (pathname === altHref || pathname.startsWith(`${altHref}/`)));
          const item = (
            <button
              key={href}
              onClick={() => router.push(href)}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12px] font-medium transition-colors",
                active
                  ? "bg-accent/10 text-accent glow-border border border-cyan-300/15"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                collapsed && "justify-center px-0"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
              {!collapsed && href === "/memory" && surfaceCount > 0 && (
                <span className="ml-auto rounded-full bg-accent/20 px-1.5 text-[10px] font-semibold text-accent">
                  {surfaceCount}
                </span>
              )}
            </button>
          );
          return collapsed ? (
            <Tooltip key={href}>
              <TooltipTrigger asChild>{item}</TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          ) : (
            item
          );
        })}
      </nav>

      {/* Conversation list */}
      <div className="mt-3 flex min-h-0 flex-1 flex-col">
        {!collapsed && (
          <div className="flex items-center gap-2 px-4 pb-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Sessions
            </span>
            {streamingConversationId && (
              <span className="flex gap-1">
                <span className="streaming-dot h-1 w-1 rounded-full bg-accent" />
                <span className="streaming-dot h-1 w-1 rounded-full bg-accent [animation-delay:150ms]" />
                <span className="streaming-dot h-1 w-1 rounded-full bg-accent [animation-delay:300ms]" />
              </span>
            )}
            <span className="flex-1" />
            <span className="font-mono text-[10px] text-muted-foreground">
              {conversations.length}
            </span>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {conversations.length === 0 ? (
            !collapsed && (
              <p className="px-2 py-2 text-[11px] leading-relaxed text-muted-foreground/70">
                No sessions yet. Start a new chat to begin.
              </p>
            )
          ) : (
            conversations.map((conv) => {
              const active = conv.id === activeConversationId;
              const streaming = conv.id === streamingConversationId;
              const row = (
                <div
                  key={conv.id}
                  onClick={() => {
                    selectConversation(conv.id);
                    goChat();
                  }}
                  className={cn(
                    "group relative flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 transition-colors",
                    active
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    collapsed && "justify-center px-0"
                  )}
                >
                  <div className="min-w-0 flex-1">
                    {!collapsed && (
                      <>
                        <div className="flex items-center gap-1.5">
                          {streaming && (
                            <span className="streaming-dot h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                          )}
                          <span className="truncate text-[12px] font-medium">
                            {conv.title}
                          </span>
                        </div>
                        <span className="text-[10px] text-muted-foreground/60">
                          {formatRelativeTime(conv.updatedAt)}
                        </span>
                      </>
                    )}
                    {collapsed && (
                      <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
                    )}
                  </div>
                  {!collapsed && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.id);
                      }}
                      className="hidden h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground/60 hover:bg-destructive/10 hover:text-red-400 group-hover:inline-flex"
                      aria-label={`Delete ${conv.title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
              return collapsed ? (
                <Tooltip key={conv.id}>
                  <TooltipTrigger asChild>{row}</TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[220px]">
                    <div className="truncate">{conv.title}</div>
                  </TooltipContent>
                </Tooltip>
              ) : (
                row
              );
            })
          )}
        </div>
      </div>

      {/* Bottom status */}
      <div
        className={cn(
          "shrink-0 border-t border-border p-2",
          collapsed && "px-1.5"
        )}
      >
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg px-2 py-1.5",
            collapsed && "justify-center px-0"
          )}
        >
          <ConnectionStatus showLabel={!collapsed} />
        </div>
      </div>
    </aside>
  );
}
