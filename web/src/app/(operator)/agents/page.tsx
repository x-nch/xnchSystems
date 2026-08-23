"use client";

import { useCallback, useEffect, useState } from "react";
import { Bot, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { agentsApi, type AgentRunDTO } from "@/lib/api/agents";
import { useConnectionState } from "@/components/layout/connection-status";

const STATUS_TONE: Record<AgentRunDTO["status"], string> = {
  QUEUED: "text-muted-foreground",
  RUNNING: "text-[var(--accent)] animate-pulse",
  DONE: "text-emerald-400",
  FAILED: "text-red-400",
};

export default function AgentsPage() {
  const connection = useConnectionState();
  const [runs, setRuns] = useState<AgentRunDTO[]>([]);
  const [prompt, setPrompt] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRuns(await agentsApi.listRuns());
    } catch {
      /* transient — next poll retries */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const dispatch = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      await agentsApi.dispatch(prompt.trim(), workspace);
      setPrompt("");
      setToast("Task dispatched — runner will claim it shortly");
      await refresh();
    } catch (e) {
      setToast(`Dispatch failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-4 md:p-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-[var(--accent)]" />
          <h1 className="text-lg font-semibold">Agents</h1>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Dispatch to opencode
        </h2>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Describe the task for the coding agent…"
          className="w-full rounded-lg border border-border bg-input p-2 text-sm text-foreground outline-none focus:border-[var(--accent)]"
        />
        <input
          value={workspace}
          onChange={(e) => setWorkspace(e.target.value)}
          placeholder="Workspace override (default ~/xnch-agents/<run-id>)"
          className="mt-2 w-full rounded-lg border border-border bg-input px-2 py-1.5 font-mono text-xs text-foreground outline-none focus:border-[var(--accent)]"
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {connection === "online" ? "gateway online" : `gateway ${connection}`}
          </span>
          <Button
            onClick={() => void dispatch()}
            disabled={busy || !prompt.trim()}
            className="btn-accent gap-1.5"
          >
            <Play className="h-3.5 w-3.5" /> {busy ? "Dispatching…" : "Dispatch"}
          </Button>
        </div>
        {toast && (
          <p
            className={`mt-3 text-xs ${toast.startsWith("Dispatch failed") ? "text-red-400" : "text-emerald-400"}`}
          >
            {toast}
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Runs
        </h2>
        {runs.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
            No runs yet — dispatch a task above.
          </p>
        ) : (
          runs.map((r) => (
            <article
              key={r.id}
              onClick={() => setSelectedId(selectedId === r.id ? null : r.id)}
              className={`cursor-pointer rounded-xl border bg-card p-3 transition-colors ${selectedId === r.id ? "border-[var(--accent)]" : "border-border hover:border-[var(--accent)]/50"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`font-mono text-xs font-semibold ${STATUS_TONE[r.status]}`}>
                  {r.status}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {new Date(r.created_at * 1000).toLocaleTimeString()}
                  {r.runner_id ? ` · ${r.runner_id}` : ""}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-foreground">{r.prompt}</p>
              <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                {r.workspace}
                {r.exit_code !== null && ` · exit ${r.exit_code}`}
              </p>
              {r.error && (
                <p className="mt-1 line-clamp-2 rounded bg-red-950/40 p-1.5 font-mono text-[10px] text-red-300">
                  {r.error}
                </p>
              )}
              {selectedId === r.id && (
                <div className="mt-3 space-y-2 border-t border-border pt-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Prompt</p>
                    <pre className="mt-1 whitespace-pre-wrap break-words rounded bg-input/60 p-2 font-mono text-xs text-foreground">{r.prompt}</pre>
                  </div>
                  {r.result_text && (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Agent response · {r.output_path?.split("/").pop()}
                      </p>
                      <pre className="mt-1 max-h-96 overflow-y-auto whitespace-pre-wrap break-words rounded bg-input/60 p-2 font-mono text-xs text-foreground">{r.result_text}</pre>
                    </div>
                  )}
                  {!r.result_text && r.status === "DONE" && (
                    <p className="text-[10px] text-muted-foreground">
                      No captured response (older run). Artifact on disk: {r.output_path}
                    </p>
                  )}
                </div>
              )}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
