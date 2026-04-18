# Runtime Architecture

---
tags:
  - #architecture
  - #runtime
  - #execution
---

How the system runs on a real machine: process boundaries, communication paths, resource allocation, concurrency model, and failure behavior.

For infrastructure layout and port assignments, see [[infra.md]]. For the logical execution flow mapped to phases, see [[execution-flow.md]].

---

## Process Map

Six processes on primary node. Each is a distinct OS process with its own memory space and failure domain.

```
┌────────────────────────────────────────────────────────────────────┐
│                        PRIMARY NODE                                │
│                                                                    │
│  CPU                                    GPU (RTX 3090, 24GB VRAM) │
│  ┌───────────────┐                       ┌──────────────────────┐  │
│  │  xnch-server  │ :8100  FastAPI+Uvicorn│  vllm-primary        │  │
│  │  (control     │                       │  Mistral-7B fp16     │  │
│  │   plane)      │                       │  ~14GB loaded        │  │
│  └───────┬───────┘                       │  PagedAttention      │  │
│          │                               └──────────┬───────────┘  │
│  ┌───────▼───────┐                                  │              │
│  │  nexi-engine  │ :8200  FastAPI+Uvicorn            │              │
│  │  (decision    │◀─────────────────────────────────┘              │
│  │   engine)     │                                                  │
│  └───────┬───────┘                                                  │
│          │                                                          │
│  ┌───────▼────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │ memory-store   │  │execution-runner  │  │  audit-logger     │   │
│  │ :8400          │  │:8500             │  │  :8600            │   │
│  │ SQLite WAL     │  │ action executor  │  │  append-only sink │   │
│  │ sqlite-vec     │  │                  │  │  UDP receive      │   │
│  └────────────────┘  └─────────────────┘  └───────────────────┘   │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                   SECONDARY NODE (optional)                        │
│                                                                    │
│  CPU                                    GPU (GTX 1650, 4GB VRAM)  │
│  ┌───────────────┐                       ┌──────────────────────┐  │
│  │  nexi-worker  │ :8201                 │  vllm-secondary      │  │
│  │  (overflow    │                       │  Mistral-7B GPTQ 4-bit│ │
│  │   reasoning)  │                       │  ~3.5GB loaded       │  │
│  └───────────────┘                       └──────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Communication Paths

All inter-process communication is HTTP/1.1 over localhost loopback. No message queue. No shared memory. No gRPC on day one.

```
CLI (subprocess or stdin)
  │
  │  POST /session/init
  ▼
xnch-server :8100
  │
  │  POST /session/start        POST /memory/read
  ├──────────────────────────▶  memory-store :8400
  │                                  │
  │  POST /session/start        (returns manifest)
  ▼                                  │
nexi-engine :8200 ◀────────────────────┘
  │
  │  HTTP POST (constrained prompt)
  ▼
vllm-primary :8300
  │
  │  (returns structured JSON options)
  ▼
nexi-engine :8200
  │
  │  GET /policy/check ×N (parallel)
  ├──────────────────────────▶  xnch-server :8100
  │
  │  POST /verdict
  ├──────────────────────────▶  xnch-server :8100
  │                                  │
  │                             (issues execution_token)
  │                             (emits audit record → :8600 UDP)
  │
  │  dispatch(action_spec, execution_token)
  ▼
execution-runner :8500
  │
  │  POST /execution/outcome (async, after completion)
  ▼
xnch-server :8100
  │
  │  callback to nexi
  ▼
nexi-engine :8200
  │
  │  POST /memory/write
  ▼
xnch-server :8100 → memory-store :8400
```

**Audit emission** is UDP fire-and-forget from xnch to audit-logger. The main request path does not block on audit write. The Decision Ledger write within audit-logger is the only synchronous-to-the-verdict operation — it is performed inside xnch before returning the verdict response (see `execution-flow.md` Step 10).

---

## CPU vs GPU Allocation

| Process | Hardware | Reason |
|---------|----------|--------|
| xnch-server | CPU only | Deterministic policy evaluation, SQLite I/O — no parallelism benefit from GPU |
| nexi-engine | CPU only | Orchestration logic, scoring, selection — fully sequential within a session |
| vllm-primary | RTX 3090 GPU | LLM inference — CUDA-required for fp16 throughput |
| memory-store | CPU + NVMe | SQLite WAL + sqlite-vec embeddings on CPU (all-MiniLM-L6-v2 is 22MB, ~15ms/query on i9) |
| execution-runner | CPU only | Subprocess dispatch, HTTP calls — I/O bound |
| audit-logger | CPU only | Sequential JSONL append — disk I/O bound |
| vllm-secondary | GTX 1650 GPU | GPTQ 4-bit fallback — 4GB VRAM ceiling |

**VRAM budget (RTX 3090, 24GB):**

| Allocation | Size |
|------------|------|
| OS + display | ~1GB |
| Mistral-7B fp16 model weights | ~14GB |
| KV cache (PagedAttention) | ~4GB |
| Headroom | ~5GB |

vLLM is configured with `gpu_memory_utilization=0.75` — hard ceiling at 18GB, leaving 5GB headroom for CUDA context and OS.

---

## Concurrency Model

### xnch-server

Single Uvicorn worker. **Async** (FastAPI + asyncio). Multiple simultaneous HTTP requests are handled via the event loop. Policy evaluation is synchronous within a request handler but does not block I/O. SQLite WAL mode allows concurrent reads without write contention.

Policy dry-run fanout (Step 6 in execution-flow.md): Nexi fires N parallel `GET /policy/check` requests. xnch handles these concurrently via asyncio — each is a separate coroutine evaluated against the same immutable policy set version.

### nexi-engine

Single Uvicorn worker. **Async** for I/O (HTTP calls to xnch, vllm). **Sync** for scoring and selection logic within a session. A session is a single request lifecycle — no parallelism within one session. Multiple sessions can run concurrently via the event loop.

### vllm-primary

Handles one generation request at a time per session (Nexi calls the model once per session). vLLM internally batches tokens via PagedAttention — the batching is transparent to the caller. If two sessions generate options simultaneously, vLLM queues the second request internally.

### memory-store

FastAPI wrapper over SQLite. SQLite WAL mode: concurrent readers do not block each other, writers serialize. The wrapper is single-process, single-worker. All writes are sequential — no concurrent writes to the same database file.

### execution-runner

Single worker. Execution is dispatched per-decision and runs asynchronously from Nexi's perspective (Nexi gets an `ACCEPTED` response immediately). The runner handles one active execution at a time per process instance. Parallelism across executions requires multiple runner instances.

---

## Startup Sequence

Dependency order is strict. A process that starts before its dependency will fail health checks and must restart.

```
1. vllm-primary (:8300)
      wait: 60–90s for model load into VRAM
      health: GET /health → {"status": "ready"}

2. memory-store (:8400)
      wait: ~2s for SQLite WAL initialization
      health: GET /health → {"status": "ready"}

3. xnch-server (:8100)
      depends on: memory-store (:8400) healthy
      wait: ~3s for policy store load + key initialization
      health: GET /health → {"status": "ready", "policy_version": "..."}

4. nexi-engine (:8200)
      depends on: xnch-server (:8100) healthy, vllm-primary (:8300) healthy
      wait: ~2s
      health: GET /health → {"status": "ready"}

5. execution-runner (:8500)
      depends on: xnch-server (:8100) healthy
      wait: ~1s
      health: GET /health → {"status": "ready"}

6. audit-logger (:8600)
      depends on: nothing (UDP receive, no upstream dependency)
      wait: ~1s
      health: GET /health → {"status": "ready"}
```

supervisord manages all six processes with `autorestart=true`. If vllm-primary fails to start within 120s, supervisord marks it FATAL and does not restart xnch or nexi (they have no inference capability without it — starting them would allow sessions that cannot complete option generation).

---

## Model Runtime Paths

Three inference paths in priority order:

```
1. PRIMARY  → vllm-primary :8300 (RTX 3090, fp16, ~800–4000ms)
               Mistral-7B-Instruct-v0.3
               Guided JSON output via vLLM sampling params

2. FALLBACK → vllm-secondary :8300 (GTX 1650, GPTQ 4-bit, ~1500–6000ms)
               Mistral-7B-Instruct-v0.1-GPTQ
               Activated when: primary timeout, primary OOM, primary FATAL

3. CPU      → llama-cpp-python (i9, ~8–15 tok/s, ~15–60s per generation)
               Activated when: both GPU nodes unavailable
               Decision record flags generation path as DEGRADED
```

Path selection is handled by nexi-engine's Model Adapter. The adapter probes the primary endpoint health before each session's option generation step. Fallback activation is automatic; no manual intervention required.

When the CPU path activates, Nexi caps `max_candidates` at 3 (from the configured default of 5) to limit generation time.

---

## Failure Handling at Runtime

| Process | Failure Mode | Runtime Response |
|---------|-------------|-----------------|
| vllm-primary | Crash / OOM | Model Adapter routes to vllm-secondary; supervisord restarts primary |
| vllm-primary | Timeout (>30s) | Nexi activates rule-based option generator; session continues as DEGRADED |
| xnch-server | Crash | All in-flight sessions fail; nexi-engine returns 503 to callers; supervisord restarts xnch |
| nexi-engine | Crash | Session fails; execution token not issued; no side effect possible; supervisord restarts |
| memory-store | Crash | xnch cannot load context manifest; returns DEGRADED; does not proceed with empty context |
| execution-runner | Crash | Execution token already issued but dispatch not confirmed; token expires (TTL); Nexi must resubmit to `/verdict` for new token |
| audit-logger | Crash | UDP packets drop silently; xnch's synchronous ledger write (inside xnch-server process) is unaffected; audit-logger restart recovers from last JSONL position |

**Session state on crash:** Sessions are stateless inside nexi-engine. If the nexi process crashes mid-session, the session context in xnch (pinned `system_state_version`, issued tokens) persists until TTL expiry. The user receives a connection error and must resubmit — the `idempotency_key` prevents duplicate episode creation on resubmission.

---

## Latency Budget per Process

From `execution-flow.md` — mapped to which process is active:

| Step | Active Process | Typical Latency |
|------|---------------|-----------------|
| Session init + actor resolve | xnch-server | 20–50ms |
| Intent interpretation | nexi-engine (CPU) | ~5ms |
| Context manifest load | xnch-server + memory-store | 80–200ms |
| Option generation | vllm-primary (GPU) | 800–4000ms |
| Parallel policy dry-run ×N | xnch-server (async) | 40–120ms |
| Scoring + simulation | nexi-engine (CPU) | 10–80ms |
| Final verdict + token issue | xnch-server | 30–60ms |
| Execution dispatch | execution-runner | 10ms (handoff) |

**Total pre-execution latency: ~1100–4600ms.** GPU inference (vllm-primary) is 70–85% of that. All other processes are fast. The optimization lever is model inference latency, not inter-process communication.

---

## Resource Arbitration

### Allocation by Work Type

Three distinct work types compete for the GPU. They are not equal in latency sensitivity or consequence.

| Work Type | GPU Consumer | Latency Sensitivity | Consequence of Delay |
|-----------|-------------|--------------------|-----------------------|
| Real-time decision (option generation) | vllm-primary | High — user is waiting | Session held open, TTL at risk |
| Outcome simulation | nexi-engine → vllm-primary | Medium — within session | Scoring delayed, but session not yet at verdict |
| Background learning (embedding updates for pattern extraction) | memory-store CPU (sqlite-vec) | Low — async, scheduled | Pattern data stale by at most one 6h cycle |

Background learning (Pattern Extractor, Score Adapter) does **not** use the GPU. sqlite-vec embedding runs on CPU via sentence-transformers. GPU contention exists only between real-time decision generation and outcome simulation, both of which occur within the same Nexi session.

### Priority Rules

```
1. Real-time decision (option generation, Step 5)       ← highest priority
2. Outcome simulation (Step 8, within same session)
3. Background learning (async, CPU-only)                ← lowest priority
```

Within a single session, option generation (Step 5) always completes before simulation (Step 8). There is no intra-session GPU contention — a session acquires the model for generation, receives results, then simulation runs as a CPU-side state projection (no additional model call). The GPU is released after Step 5.

Cross-session GPU contention occurs when two sessions reach Step 5 simultaneously.

### Queueing Strategy

vLLM manages its own internal request queue with First-In-First-Out semantics across sessions. Nexi does not implement an application-level queue — it submits to vLLM and awaits response. Sessions arriving simultaneously are serialized inside vLLM's scheduler. vLLM's PagedAttention batches tokens across concurrent requests where possible; at the generation level (not batching), requests are effectively FIFO.

There is no priority queue at the vLLM boundary — all real-time decision requests are treated as equal priority by the model runtime. Priority differentiation (e.g., `CRITICAL` urgency sessions ahead of `NORMAL`) is a future capability requiring a vLLM-side scheduler or application-level request gating in Nexi.

### Contention Handling

When vllm-primary is processing a request and a second session reaches Step 5:

1. Second session's HTTP POST to vllm-primary `:8300` is accepted and queued inside vLLM
2. vLLM begins processing when the current generation slot frees
3. The second session's `execution_token` TTL (30s, set at Step 10) is **not** started yet — token is issued only after verdict (Step 10), which requires scoring to complete first. Generation queue time does not consume token TTL.
4. If generation wait exceeds 30s (configurable timeout in Nexi's Model Adapter), the session treats it as a timeout and activates the fallback chain

No requests are dropped due to contention. Contention manifests as increased end-to-end session latency, not as failures.

### Fallback Chain on GPU Unavailability

```
1. vllm-primary (:8300, RTX 3090 fp16)
      │ — timeout > 30s, OOM, or FATAL
      ▼
2. vllm-secondary (:8300 on secondary node, GTX 1650 GPTQ 4-bit)
      │ — timeout > 45s, unavailable, or secondary node down
      ▼
3. llama-cpp-python (i9 CPU, ~8–15 tok/s)
      │ — max_candidates reduced from 5 → 3
      │ — generation_path = RULE_BASED flagged in Decision Record
      │ — ~15–60s per generation (acceptable for non-interactive sessions)
      ▼
4. Rule-based option generator (policy memory only, no model call)
      — activated when all inference paths fail
      — 3 hardcoded conservative options from active policy memory
      — fastest path; no model involved
```

Fallback to step 4 (rule-based, no inference) is the floor. The system always produces a decision — it never returns an empty option set due to infrastructure failure.

### Concurrency Limits

| Device | Max Parallel Inference Requests | Basis |
|--------|--------------------------------|-------|
| RTX 3090 (vllm-primary) | 1 active generation at a time | Single PagedAttention generation slot per vLLM instance; batching is at token level, not request level |
| GTX 1650 (vllm-secondary) | 1 active generation at a time | Same — single vLLM instance on secondary node |
| i9 CPU (llama-cpp-python) | 1 | Single-threaded inference; parallelism at token level only |
| memory-store (sqlite-vec embeddings) | Concurrent reads; serialized writes | SQLite WAL mode; embedding queries (CPU) are read-only and concurrent |

To handle more than 1 concurrent real-time session without queue wait, a second vllm-primary instance on the same GPU is required — not a second GPU. vLLM supports tensor-parallel and pipeline-parallel modes, but that configuration is outside single-node scope. For now: one active generation at a time; queue depth is the scaling metric to monitor.

---

## Related

- [[_system-map.md]]
- [[execution-flow.md]]
