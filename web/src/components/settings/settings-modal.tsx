"use client";

import { useState } from "react";
import { CircleCheck, CircleX, PlugZap } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { endpoints } from "@/lib/api/endpoints";
import type { AuthMode } from "@/lib/auth/auth";

const AUTH_MODES: { value: AuthMode; label: string; hint: string }[] = [
  { value: "actor", label: "Dev actor", hint: "Authorization: actor:<id> — accepted by the local gateway in dev mode" },
  { value: "jwt", label: "Minted JWT", hint: "HS256 JWT signed in-browser with XNCH_AUTH_SECRET (matches the CLI)" },
  { value: "token", label: "Bearer token", hint: "Paste an externally-minted HS256 token" },
];

export function SettingsModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const settings = useSettingsStore();
  const [testResult, setTestResult] = useState<"idle" | "ok" | "fail">("idle");
  const [testing, setTesting] = useState(false);
  const [detail, setDetail] = useState("");

  const runTest = async () => {
    setTesting(true);
    setTestResult("idle");
    setDetail("");
    try {
      const health = await endpoints.health();
      setTestResult("ok");
      setDetail(
        `status=${health.status} · redis=${health.redis} · state_v=${health.state_version}`
      );
    } catch (err) {
      setTestResult("fail");
      setDetail(err instanceof Error ? err.message : "Request failed");
    } finally {
      setTesting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Connection and identity for the xnch gateway.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 px-5 py-3">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <div className="flex items-center gap-2">
              <PlugZap className="h-3.5 w-3.5 text-accent" />
              <span className="text-xs font-semibold">Gateway connection</span>
            </div>
            <p className="mt-1 font-mono text-[11px] leading-relaxed text-muted-foreground">
              Browser → /api/gateway → {process.env.NEXT_PUBLIC_GATEWAY_URL || "http://192.168.1.10:8001"}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground/80">
              Requests are proxied same-origin by the Next.js server, so the
              backend never needs CORS. Point it at another host by setting
              <code className="mx-1 rounded bg-muted px-1 py-px font-mono">XNCH_GATEWAY_URL</code>
              before starting the dev server.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={runTest}
              disabled={testing}
            >
              {testing ? "Testing…" : "Test connection"}
            </Button>
            {testResult !== "idle" && (
              <div
                className={
                  testResult === "ok"
                    ? "mt-2 flex items-start gap-1.5 text-emerald-400"
                    : "mt-2 flex items-start gap-1.5 text-red-400"
                }
              >
                {testResult === "ok" ? (
                  <CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                ) : (
                  <CircleX className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                )}
                <span className="text-[11px] leading-relaxed">{detail}</span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="actor-id">Actor ID</Label>
              <Input
                id="actor-id"
                value={settings.actorId}
                onChange={(e) => settings.setActorId(e.target.value)}
                placeholder="operator"
                className="font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="actor-role">Actor role</Label>
              <Input
                id="actor-role"
                value={settings.actorRole}
                onChange={(e) => settings.setActorRole(e.target.value)}
                placeholder="operator"
                className="font-mono"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Auth mode</Label>
            <div className="grid grid-cols-3 gap-2">
              {AUTH_MODES.map((mode) => (
                <button
                  key={mode.value}
                  onClick={() => settings.setAuthMode(mode.value)}
                  className={
                    settings.authMode === mode.value
                      ? "rounded-lg border border-accent/60 bg-accent-subtle px-2 py-2 text-left transition-colors"
                      : "rounded-lg border border-border bg-muted/30 px-2 py-2 text-left transition-colors hover:bg-muted"
                  }
                >
                  <span className="block text-xs font-medium">{mode.label}</span>
                </button>
              ))}
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {
                AUTH_MODES.find((m) => m.value === settings.authMode)?.hint
              }
            </p>
            {settings.authMode === "jwt" && (
              <div className="space-y-1.5 pt-1">
                <Label htmlFor="auth-secret">XNCH_AUTH_SECRET</Label>
                <Input
                  id="auth-secret"
                  type="password"
                  value={settings.authSecret}
                  onChange={(e) => settings.setAuthSecret(e.target.value)}
                  placeholder="shared secret for HS256 signing"
                  className="font-mono"
                />
              </div>
            )}
            {settings.authMode === "token" && (
              <div className="space-y-1.5 pt-1">
                <Label htmlFor="pasted-token">Bearer token</Label>
                <Input
                  id="pasted-token"
                  value={settings.pastedToken}
                  onChange={(e) => settings.setPastedToken(e.target.value)}
                  placeholder="eyJhbGciOiJIUzI1NiIs…"
                  className="font-mono"
                />
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Badge tone="muted" className="mr-auto font-mono">
            actor:{settings.actorId} @ {settings.actorRole}
          </Badge>
          <Button onClick={() => onOpenChange(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
