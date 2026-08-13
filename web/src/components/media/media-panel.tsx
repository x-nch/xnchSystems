"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Clapperboard,
  Film,
  Image as ImageIcon,
  Loader2,
  Play,
  ScanEye,
  Sparkles,
  Upload,
  Wand2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils/cn";
import {
  MEDIA_ACCEPT,
  createMediaJob,
  getMediaJob,
  isTerminal,
  listMediaJobs,
  mediaUrl,
  uploadMedia,
} from "@/lib/api/media";
import type { MediaJob, MediaTaskMeta } from "@/lib/api/media-types";
import { useHydrated } from "@/lib/hooks/use-hydrated";

const TASKS: MediaTaskMeta[] = [
  {
    name: "understand",
    label: "Understand",
    description: "Caption / summarize an image or video (Qwen2.5-VL)",
    minInputs: 1,
    maxInputs: 4,
    requiresPrompt: false,
    output: "text",
  },
  {
    name: "generate_image",
    label: "Generate image",
    description: "Text → Flux image",
    minInputs: 0,
    maxInputs: 0,
    requiresPrompt: true,
    output: "image",
  },
  {
    name: "edit_image",
    label: "Edit image",
    description: "Transform / restyle an image (Flux)",
    minInputs: 1,
    maxInputs: 2,
    requiresPrompt: true,
    output: "image",
  },
  {
    name: "upscale_image",
    label: "Upscale",
    description: "2× upscale an image (Flux)",
    minInputs: 1,
    maxInputs: 1,
    requiresPrompt: false,
    output: "image",
  },
  {
    name: "image_to_video",
    label: "Image → Video",
    description: "Animate a still with Wan 2.2",
    minInputs: 1,
    maxInputs: 1,
    requiresPrompt: true,
    output: "video",
  },
  {
    name: "text_to_video",
    label: "Text → Video",
    description: "Wan 2.2 from a prompt",
    minInputs: 0,
    maxInputs: 0,
    requiresPrompt: true,
    output: "video",
  },
  {
    name: "video_to_video",
    label: "Video → Video",
    description: "Restyle an existing video (Wan 2.2)",
    minInputs: 1,
    maxInputs: 1,
    requiresPrompt: true,
    output: "video",
  },
];

const TASK_ICONS: Record<string, typeof ScanEye> = {
  understand: ScanEye,
  generate_image: Sparkles,
  edit_image: Wand2,
  upscale_image: ImageIcon,
  image_to_video: Clapperboard,
  text_to_video: Film,
  video_to_video: Wand2,
};

const STATUS_TONE: Record<MediaJob["status"], "muted" | "accent" | "success" | "destructive"> = {
  queued: "muted",
  running: "accent",
  done: "success",
  failed: "destructive",
};

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function MediaPanel() {
  const hydrated = useHydrated();
  const queryClient = useQueryClient();
  const [taskName, setTaskName] = useState<string>("understand");
  const [files, setFiles] = useState<File[]>([]);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<MediaJob | null>(null);
  const [showRecent, setShowRecent] = useState<MediaJob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const task = TASKS.find((t) => t.name === taskName) ?? TASKS[0];

  const { data: recent = [], refetch: refetchRecent } = useQuery({
    queryKey: ["media-jobs"],
    queryFn: () => listMediaJobs(12),
    refetchInterval: 10_000,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!activeJob || isTerminal(activeJob.status)) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const job = await getMediaJob(activeJob.job_id);
        setActiveJob(job);
        if (isTerminal(job.status)) {
          void queryClient.invalidateQueries({ queryKey: ["media-jobs"] });
        }
      } catch {
        // transient poll failure — keep last state
      }
    }, 1500);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeJob, queryClient]);

  const onFiles = (list: FileList | null) => {
    if (!list) return;
    setFiles(Array.from(list));
    setError(null);
  };

  const run = async () => {
    setError(null);
    if (files.length < task.minInputs || files.length > task.maxInputs) {
      setError(
        `${task.label} needs ${task.minInputs}-${task.maxInputs} file${task.maxInputs === 1 ? "" : "s"} (got ${files.length})`
      );
      return;
    }
    if (task.requiresPrompt && !prompt.trim()) {
      setError("This task needs a prompt.");
      return;
    }
    for (const f of files) {
      if (!f.type.startsWith("image/") && !f.type.startsWith("video/")) {
        setError(`Unsupported file type: ${f.name}`);
        return;
      }
    }

    setBusy(true);
    try {
      const inputIds: string[] = [];
      for (const f of files) {
        const record = await uploadMedia(f);
        inputIds.push(record.file_id);
      }
      const job = await createMediaJob({
        task: task.name,
        prompt: prompt.trim(),
        input_file_ids: inputIds,
      });
      setActiveJob(job);
      setShowRecent(null);
      setFiles([]);
      setPrompt("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      void queryClient.invalidateQueries({ queryKey: ["media-jobs"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Job failed to start");
    } finally {
      setBusy(false);
    }
  };

  const openJob = async (jobId: string) => {
    const job = await getMediaJob(jobId);
    setShowRecent(job);
    setActiveJob(null);
  };

  if (!hydrated) {
    return (
      <div className="flex h-full items-center justify-center">
        <span className="font-mono text-[12px] text-muted-foreground">Loading…</span>
      </div>
    );
  }

  const displayJob = showRecent ?? activeJob;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
        <header className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Clapperboard className="h-4.5 w-4.5" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">Media Studio</h1>
            <p className="text-[11px] text-muted-foreground">
              Local image + video model stack on Node B (RTX 3090)
            </p>
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-red-400">
            {error}
          </div>
        )}

        {/* Task picker */}
        <Card>
          <CardHeader>
            <CardTitle>Task</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {TASKS.map((t) => {
                const Icon = TASK_ICONS[t.name] ?? ScanEye;
                const active = t.name === taskName;
                return (
                  <button
                    key={t.name}
                    onClick={() => {
                      setTaskName(t.name);
                      setError(null);
                    }}
                    className={cn(
                      "flex flex-col gap-1 rounded-lg border p-2.5 text-left transition-colors",
                      active
                        ? "border-accent/40 bg-accent/10"
                        : "border-border bg-transparent hover:bg-muted/50"
                    )}
                  >
                    <span
                      className={cn(
                        "flex items-center gap-1.5 text-[12px] font-medium",
                        active ? "text-accent" : "text-foreground"
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {t.label}
                    </span>
                    <span className="text-[10px] leading-snug text-muted-foreground">
                      {t.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Upload */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-3.5 w-3.5 text-accent" />
              Media
              <span className="ml-auto font-mono text-[10px] font-normal text-muted-foreground">
                {task.minInputs}-{task.maxInputs} required
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-border bg-muted/20 px-3 py-6 transition-colors hover:bg-muted/40"
            >
              <Upload className="h-5 w-5 text-muted-foreground" />
              <span className="text-[12px] text-muted-foreground">
                Click to choose files (png / jpg / webp / mp4 / mov)
              </span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={MEDIA_ACCEPT}
              className="hidden"
              onChange={(e) => onFiles(e.target.files)}
            />
            {files.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {files.map((f, i) => (
                  <Badge key={i} tone="accent">
                    {f.name}
                    <span className="opacity-70">{formatBytes(f.size)}</span>
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Prompt */}
        <Card>
          <CardHeader>
            <CardTitle>Prompt</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                task.name === "understand"
                  ? "e.g. Summarize what is happening in this video"
                  : task.name === "generate_image"
                    ? "e.g. A lone astronaut on a neon Mars, cinematic lighting"
                    : "Describe how the input should change…"
              }
              rows={3}
              disabled={!task.requiresPrompt}
            />
          </CardContent>
        </Card>

        <div className="flex items-center gap-3">
          <Button onClick={run} disabled={busy} size="lg">
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {busy ? "Dispatching…" : "Run"}
          </Button>
          <span className="font-mono text-[11px] text-muted-foreground">
            engine: {task.output === "text" ? "qwen-vl" : "comfyui"}
          </span>
        </div>

        {/* Active job */}
        {displayJob && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {TASK_ICONS[displayJob.task] && (() => {
                  const Icon = TASK_ICONS[displayJob.task];
                  return <Icon className="h-3.5 w-3.5 text-accent" />;
                })()}
                {TASKS.find((t) => t.name === displayJob.task)?.label ?? displayJob.task}
                <span className="ml-auto flex items-center gap-1.5">
                  {displayJob.status === "running" && (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  )}
                  <Badge tone={STATUS_TONE[displayJob.status]}>{displayJob.status}</Badge>
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {displayJob.error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-red-400">
                  {displayJob.error}
                </div>
              )}
              {displayJob.duration_ms != null && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {(displayJob.duration_ms / 1000).toFixed(1)}s
                </span>
              )}
              {displayJob.result_text && (
                <pre className="whitespace-pre-wrap rounded-lg bg-muted/30 p-3 font-mono text-[12px] text-foreground">
                  {displayJob.result_text}
                </pre>
              )}
              {displayJob.output_files.length > 0 && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {displayJob.output_files.map((out) =>
                    out.content_type.startsWith("video/") ? (
                      <video
                        key={out.file_id}
                        src={mediaUrl(out.file_id)}
                        controls
                        className="max-h-72 w-full rounded-lg border border-border bg-black"
                      />
                    ) : (
                      <img
                        key={out.file_id}
                        src={mediaUrl(out.file_id)}
                        alt={out.filename}
                        className="w-full rounded-lg border border-border"
                      />
                    )
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Recent jobs */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Recent jobs
              <button
                onClick={() => void refetchRecent()}
                className="ml-auto text-[10px] font-normal text-muted-foreground hover:text-foreground"
              >
                refresh
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recent.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">No jobs yet.</p>
            ) : (
              <div className="flex flex-col gap-1">
                {recent.map((job) => (
                  <button
                    key={job.job_id}
                    onClick={() => void openJob(job.job_id)}
                    className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-muted/50"
                  >
                    <span className="truncate text-[12px]">
                      {TASKS.find((t) => t.name === job.task)?.label ?? job.task}
                    </span>
                    <span className="ml-auto flex items-center gap-1.5">
                      <Badge tone={STATUS_TONE[job.status]}>{job.status}</Badge>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
