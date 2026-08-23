"use client";

import { X, Focus, GitBranch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HudCard, HudCardContent, HudCardHeader, HudCardTitle } from "@/components/ui/hud-card";
import type { GraphEntity, GraphRelation } from "@/lib/api/types";
import { colorForEntityType } from "./force-layout";
import { formatPercent } from "@/lib/utils/format";

export function EntityPanel({
  entity,
  relations,
  onClose,
  onFocus,
  onNavigate,
}: {
  entity: GraphEntity;
  relations: GraphRelation[];
  onClose: () => void;
  onFocus: () => void;
  onNavigate: (entityId: string) => void;
}) {
  const color = colorForEntityType(entity.type);
  const connected = relations.filter(
    (r) => r.from_id === entity.entity_id || r.to_id === entity.entity_id
  );

  return (
    <HudCard glow="attention" className="flex h-full flex-col">
      <HudCardHeader className="flex-row items-start justify-between gap-2">
        <div className="min-w-0">
          <HudCardTitle className="truncate normal-case tracking-normal text-foreground">
            {entity.name}
          </HudCardTitle>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge tone="accent" className="font-mono" style={{ color, borderColor: `${color}44` }}>
              {entity.type}
            </Badge>
            <span className="font-mono text-[9px] text-muted-foreground">
              {entity.entity_id.slice(0, 12)}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Close panel"
        >
          <X className="h-4 w-4" />
        </button>
      </HudCardHeader>

      <HudCardContent className="min-h-0 flex-1 space-y-3 overflow-y-auto">
        {entity.created_at && (
          <p className="font-mono text-[10px] text-muted-foreground">
            created {new Date(entity.created_at).toLocaleString()}
          </p>
        )}

        <div className="flex gap-2">
          <Button size="sm" onClick={onFocus} className="flex-1">
            <Focus className="h-3.5 w-3.5" />
            Focus
          </Button>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
            <GitBranch className="h-3 w-3" />
            Relations ({connected.length})
          </div>
          {connected.length === 0 ? (
            <p className="text-[11px] text-muted-foreground/70">No relations in current view.</p>
          ) : (
            <ul className="space-y-1.5">
              {connected.map((rel, i) => {
                const outbound = rel.from_id === entity.entity_id;
                const otherId = outbound ? rel.to_id : rel.from_id;
                const otherName = outbound ? rel.to_name : rel.from_name;
                return (
                  <li key={`${rel.from_id}-${rel.to_id}-${rel.rel_type}-${i}`}>
                    <button
                      onClick={() => onNavigate(otherId)}
                      className="w-full rounded-lg border border-border/60 bg-card/50 px-2.5 py-2 text-left transition-colors hover:border-[var(--state-attention)]/20 hover:bg-[var(--accent-subtle)]"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[10px] text-amber-200">{rel.rel_type}</span>
                        <span className="text-[9px] text-muted-foreground">
                          {outbound ? "→" : "←"}
                        </span>
                        <span className="truncate font-mono text-[10px] text-foreground">
                          {otherName ?? otherId}
                        </span>
                        <span className="ml-auto font-mono text-[9px] text-muted-foreground">
                          {formatPercent(rel.confidence)}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </HudCardContent>
    </HudCard>
  );
}
