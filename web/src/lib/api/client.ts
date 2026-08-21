import { useSettingsStore } from "@/lib/stores/settings-store";
import { buildAuthorization } from "@/lib/auth/auth";
import type { StreamEvent } from "@/lib/api/types";
import type { GraphStreamEvent } from "@/lib/api/types";

export const API_BASE = "/api/gateway";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function buildHeaders(): Promise<Record<string, string>> {
  const settings = useSettingsStore.getState();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Actor-Role": settings.actorRole || "operator",
  };
  const auth = await buildAuthorization({
    mode: settings.authMode,
    actorId: settings.actorId,
    authSecret: settings.authSecret,
    pastedToken: settings.pastedToken,
  });
  if (auth) headers["Authorization"] = auth;
  return headers;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, query, headers: extraHeaders, signal } = options;

  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value != null) url.searchParams.set(key, String(value));
    }
  }

  const headers = { ...(await buildHeaders()), ...extraHeaders };
  let payload: string | undefined;
  if (body !== undefined) payload = JSON.stringify(body);

  let resp: Response;
  try {
    resp = await fetch(url, {
      method,
      headers,
      body: payload,
      signal,
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "Cannot reach xnch gateway");
  }

  if (!resp.ok) {
    let detail: unknown = resp.statusText;
    try {
      const data = await resp.json();
      detail = data.detail ?? data;
    } catch {
      /* keep text status */
    }
    throw new ApiError(resp.status, detail);
  }

  const text = await resp.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

/**
 * Open an SSE stream and normalize the events emitted by /nexi/chat/stream.
 *
 * The backend currently emits a single `{content}` chunk followed by `[DONE]`,
 * but the parser also understands `delta`, `tool_call`, `tool_result`, `meta`
 * and `error` payloads so true token streaming and tool visibility slot in
 * without a frontend change.
 */
export async function streamChatEvents(
  body: { session_id: string; message: string; actor_role?: string },
  options: {
    signal: AbortSignal;
    onEvent: (event: StreamEvent) => void;
  }
): Promise<void> {
  const { signal, onEvent } = options;
  const url = `${API_BASE}/nexi/chat/stream`;
  const headers = await buildHeaders();

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: { ...headers, Accept: "text/event-stream" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      onEvent({ type: "error", message: "Generation stopped" });
      return;
    }
    onEvent({ type: "error", message: "Cannot reach xnch gateway" });
    return;
  }

  if (!resp.ok) {
    let message = `Stream failed (${resp.status})`;
    try {
      const data = await resp.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      /* keep default */
    }
    onEvent({ type: "error", message });
    return;
  }

  const reader = resp.body?.getReader();
  if (!reader) {
    onEvent({ type: "error", message: "No response body" });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      emitRawEvent(rawEvent, onEvent);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) emitRawEvent(buffer, onEvent);
  onEvent({ type: "done" });
}

/** SSE stream for live Kuzu graph mutations. */
export async function streamGraphEvents(options: {
  signal: AbortSignal;
  onEvent: (event: GraphStreamEvent) => void;
}): Promise<void> {
  const { signal, onEvent } = options;
  const url = `${API_BASE}/memory/graph/stream`;
  const headers = await buildHeaders();

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "GET",
      headers: { ...headers, Accept: "text/event-stream" },
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    onEvent({ type: "error", message: "Cannot reach xnch gateway" });
    return;
  }

  if (!resp.ok) {
    onEvent({ type: "error", message: `Graph stream failed (${resp.status})` });
    return;
  }

  const reader = resp.body?.getReader();
  if (!reader) {
    onEvent({ type: "error", message: "No response body" });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      emitGraphRawEvent(rawEvent, onEvent);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) emitGraphRawEvent(buffer, onEvent);
  onEvent({ type: "done" });
}

function emitGraphRawEvent(
  rawEvent: string,
  onEvent: (e: GraphStreamEvent) => void
): void {
  let data = "";
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;

  try {
    const payload = JSON.parse(data) as GraphStreamEvent;
    onEvent(payload);
  } catch {
    /* ignore malformed frames */
  }
}

function emitRawEvent(rawEvent: string, onEvent: (e: StreamEvent) => void): void {
  let data = "";
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("data:")) {
      data += line.slice(5).trim();
    }
  }
  if (!data) return;

  if (data === "[DONE]") {
    onEvent({ type: "done" });
    return;
  }

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data) as Record<string, unknown>;
  } catch {
    return;
  }

  if (payload.error != null) {
    onEvent({ type: "error", message: String(payload.error) });
  } else if (typeof payload.content === "string" && payload.content.length > 0) {
    onEvent({ type: "content", content: payload.content });
  } else if (typeof payload.delta === "string" && payload.delta.length > 0) {
    onEvent({ type: "delta", delta: payload.delta });
  } else if (payload.tool_call != null) {
    onEvent({
      type: "tool_call",
      tool: String(payload.tool ?? "tool"),
      arguments: payload.arguments,
    });
  } else if (payload.tool_result != null) {
    onEvent({
      type: "tool_result",
      tool: String(payload.tool ?? "tool"),
      result: payload.result,
    });
  } else {
    onEvent({ type: "meta", ...payload });
  }
}
