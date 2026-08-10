"use client";

import { useState } from "react";
import { X, Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { useMcpCall } from "@/lib/api/hooks";
import type { McpTool } from "@/lib/api/types";

const TIER_TONE: Record<string, "accent" | "success" | "warning" | "muted" | "destructive"> = {
  T0_READ: "destructive",
  T1_WRITE: "warning",
  T2_EXEC: "accent",
  T3_SAFE: "muted",
};

export function ToolCallModal({
  tool,
  onOpenChange,
}: {
  tool: McpTool | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={tool !== null} onOpenChange={(open) => !open && onOpenChange(false)}>
      {tool && (
        <ToolCallModalBody
          key={tool.name}
          tool={tool}
          onClose={() => onOpenChange(false)}
        />
      )}
    </Dialog>
  );
}

function ToolCallModalBody({
  tool,
  onClose,
}: {
  tool: McpTool;
  onClose: () => void;
}) {
  const [argsText, setArgsText] = useState("{}");
  const [parseError, setParseError] = useState<string | null>(null);
  const call = useMcpCall();

  const run = () => {
    setParseError(null);
    let args: Record<string, unknown>;
    try {
      args = argsText.trim() ? JSON.parse(argsText) : {};
      if (typeof args !== "object" || args === null || Array.isArray(args)) {
        throw new Error("Arguments must be a JSON object");
      }
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Invalid JSON");
      return;
    }
    call.mutate({ name: tool.name, arguments: args });
  };

  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 font-mono">
          {tool.name}
          <Badge tone={TIER_TONE[tool.tier] ?? "muted"}>{tool.tier}</Badge>
        </DialogTitle>
        <DialogDescription className="pt-1 leading-relaxed">
          {tool.description || "No description"}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-3 px-5 py-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Arguments (JSON)
          </label>
          <textarea
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            spellCheck={false}
            className="h-32 w-full resize-none rounded-lg border border-border bg-input p-3 font-mono text-[12px] text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          />
          {parseError && <p className="mt-1 text-[11px] text-red-400">{parseError}</p>}
        </div>

        {call.isPending && (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-[12px] text-muted-foreground">
            <Spinner className="h-3.5 w-3.5 text-accent" />
            Invoking {tool.name} via {`POST /mcp/call`}…
          </div>
        )}

        {call.data && (
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Result
            </label>
            <pre className="max-h-64 overflow-auto rounded-lg border border-border bg-code-bg p-3 font-mono text-[12px] leading-relaxed text-emerald-300">
              {JSON.stringify(call.data.result, null, 2)}
            </pre>
          </div>
        )}

        {call.isError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-[12px] text-red-300">
            {call.error instanceof Error ? call.error.message : "Call failed"}
          </div>
        )}
      </div>

      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          <X className="h-3.5 w-3.5" />
          Close
        </Button>
        <Button onClick={run} disabled={call.isPending}>
          <Play className="h-3.5 w-3.5" />
          {call.isPending ? "Running…" : "Call tool"}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
