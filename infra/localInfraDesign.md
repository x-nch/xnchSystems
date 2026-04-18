xnch/Nexi Local Infrastructure Design
Hardware Reality Check First
Before assigning workloads, establish what each GPU can actually hold:
RTX 3090 — 24GB VRAM budget:
Primary LLM (quantized 13B-30B range)   ~8–16GB
Nexi working context + embeddings        ~2GB
Inference overhead + KV cache            ~3GB
Safety headroom                          ~3GB
Usable: comfortable dual-model operation
GTX 1650 — 4GB VRAM budget:
Small quantized model (3B max, Q4)       ~2–2.5GB
Embedding model                          ~0.5GB
Overhead                                 ~0.5GB
Usable: one small model OR one embedding model, not both simultaneously
This constraint is the primary design driver. The 1650 cannot run reasoning workloads. It runs classification, routing, and embedding — or it offloads to CPU entirely.

1. Component Distribution Across Nodes
Primary Node (i9 + 3090): Nexi + Model Layer
┌─────────────────────────────────────────────┐
│              PRIMARY NODE                   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │         Nexi Process                │   │
│  │  - Intent Interpreter               │   │
│  │  - Option Generator (model calls)   │   │
│  │  - Option Evaluator                 │   │
│  │  - Outcome Simulator                │   │
│  │  - Decision Selector                │   │
│  │  runs on: i9 CPU                    │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │         Model Layer                 │   │
│  │  - Primary LLM (vLLM/llama.cpp)    │   │
│  │  - Embedding model                  │   │
│  │  runs on: RTX 3090                  │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
Nexi itself runs on CPU — it is orchestration logic, not matrix multiplication. The 3090 is reserved exclusively for model inference. Nexi calls the model via local HTTP (vLLM OpenAI-compatible endpoint on localhost:8000).
Secondary Node (i7 + 1650): xnch + Background Processing
┌─────────────────────────────────────────────┐
│              SECONDARY NODE                 │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │         xnch Process                │   │
│  │  - Policy Engine                    │   │
│  │  - Governance Layer (RBAC)          │   │
│  │  - Audit Logger                     │   │
│  │  - Execution Gate                   │   │
│  │  - Memory Store (all three types)   │   │
│  │  runs on: i7 CPU                    │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │      Background Processing          │   │
│  │  - Pattern extraction               │   │
│  │  - Weight optimization              │   │
│  │  - Policy candidate generation      │   │
│  │  - Audit log compaction             │   │
│  │  runs on: i7 CPU                    │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │      Optional GPU Use (1650)        │   │
│  │  - Small classifier model           │   │
│  │  - Intent pre-classification        │   │
│  │  - Only if model fits in 4GB        │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
xnch is deterministic rule evaluation and database I/O — it has zero GPU requirement. Placing it on the secondary node frees the primary node entirely for inference throughput, and isolates the control plane from compute pressure. If the primary node is saturated with a long inference run, xnch keeps operating independently.

2. Task Assignment by Hardware
i9 + RTX 3090 — Primary Node Tasks
TaskCPU/GPURationalePrimary LLM inference (option generation)3090Core VRAM consumerEmbedding generation for context retrieval3090Fast, parallelizable with main modelNexi orchestration logici9 CPUPure compute, no GPU neededOption scoring computationi9 CPUMath, not matrix opsOutcome simulation (forward projection)i9 CPUStructured computationContext manifest assemblyi9 CPUMemory + logic workvLLM server process3090Model host
i7 + GTX 1650 — Secondary Node Tasks
TaskCPU/GPURationalexnch policy evaluationi7 CPUDeterministic DSL evaluationPostgreSQL (episodic + semantic memory)i7 CPUI/O bound, not compute boundetcd (policy memory)i7 CPUConsensus store, CPU onlyAudit log writesi7 CPUAppend-only I/OPattern extraction (batch)i7 CPUAggregation queries, scheduledWeight optimization (batch)i7 CPUSimple math over query resultsIntent pre-classifier (optional)1650Only if model ≤ 2GB — Phi-3-mini Q4Audit log compactioni7 CPUOff-peak scheduled job
1650 usage policy: Load a model onto the 1650 only if it fits within 2.5GB (leaving headroom). Candidate: Phi-3-mini at Q4 (~1.8GB) for intent pre-classification. If the classification confidence is high enough (>0.85), Nexi skips its own intent interpretation pass — saves a round trip. If the 1650 is unavailable or the model doesn't fit, intent classification runs on the i7 CPU with a rule-based fallback classifier. The 1650 is an optimization, never a dependency.

3. Model Allocation Strategy
Primary LLM — RTX 3090
Default recommendation: Mistral-7B or Mixtral-8x7B (Q4_K_M quantization) via llama.cpp or vLLM.
Mistral-7B  Q4_K_M:  ~4.1GB  VRAM — leaves 19.9GB headroom, very comfortable
Mixtral-8x7B Q4_K_M: ~26GB   VRAM — does NOT fit, requires offloading
Llama-3-8B  Q4_K_M:  ~4.7GB  VRAM — good option
Llama-3-13B Q4_K_M:  ~8.0GB  VRAM — solid reasoning quality, fits well
Recommended allocation:
Primary reasoning LLM:   Llama-3-13B Q4_K_M     ~8GB VRAM
Embedding model:         nomic-embed-text v1.5   ~0.5GB VRAM
KV cache + overhead:     ~4GB VRAM
Total:                   ~12.5GB / 24GB used
Headroom:                ~11.5GB  ← available for second model or larger batch
The headroom allows loading a second model for specialized tasks (code generation, structured output) without evicting the primary model.
When to Use Local vs External Models
Local always, external on explicit escalation only. This is a local-first system — external model calls are not a fallback path, they are an explicit operator decision.
python# Decision logic in Nexi's Option Generator

def select_model(intent: Intent, context: ContextManifest) -> ModelTarget:

    # Always try local first
    if intent.complexity == LOW:
        return LOCAL_PRIMARY          # Llama-3-13B on 3090

    if intent.complexity == MEDIUM:
        return LOCAL_PRIMARY          # same, larger context window

    if intent.complexity == HIGH:
        if vram_available() > 8GB:
            return LOCAL_PRIMARY      # still local
        else:
            return LOCAL_PRIMARY_DEGRADED  # reduce batch size, still local

    # External only if explicitly configured AND operator has enabled
    if intent.requires_external and config.allow_external:
        return EXTERNAL_API           # Claude/GPT as last resort
    
    # Default: never leave local without explicit config
    return LOCAL_PRIMARY
External model scenarios (all require explicit operator enable flag):

Intent class requires capabilities provably beyond local model
Primary node GPU is down and task cannot wait for recovery
Operator explicitly routes a specific session externally for comparison/audit

External calls are logged in xnch audit trail as actor_type: EXTERNAL_MODEL with the API endpoint, model name, and response hash. They are never transparent — the audit trail always knows when the system left local.

4. Inter-Node Communication
Simple. No service mesh, no message broker, no gRPC unless needed. Start with HTTP over LAN.
Physical connection: Direct ethernet or LAN switch. Assign static IPs:
primary.local    192.168.1.10
secondary.local  192.168.1.20
Communication pattern:
Primary (Nexi) → Secondary (xnch): HTTP REST
Secondary (xnch) → Primary (Nexi): HTTP REST callback

All calls are synchronous except audit log emission (async fire-and-forget with local queue)
Nexi → xnch calls (primary → secondary):
POST http://192.168.1.20:7000/verdict
POST http://192.168.1.20:7000/memory/read
POST http://192.168.1.20:7000/memory/write
GET  http://192.168.1.20:7000/policy/check
GET  http://192.168.1.20:7000/system/state
POST http://192.168.1.20:7000/audit/query
xnch → Nexi callbacks (secondary → primary):
POST http://192.168.1.10:7001/callbacks/outcome
POST http://192.168.1.10:7001/callbacks/state-change
Transport hardening (minimum viable):
- Mutual TLS with self-signed certs (mkcert for local CA)
- Shared secret header: X-XNCH-Node-Token: <static secret>
- Request timeout: 2000ms for verdict calls, 500ms for state reads
- No request retries on verdict — timeout escalates to operator, doesn't retry
Async audit queue:
Audit events are fire-and-forget from Nexi's perspective, but guaranteed-delivery from xnch's perspective. Nexi writes audit events to a local SQLite queue on the primary node. A background goroutine/thread drains this queue to xnch at 100ms intervals. If xnch is unreachable, the queue holds up to 10,000 events before Nexi enters degraded mode (no new decisions until audit backlog clears or operator overrides).
Primary Node:
  audit_queue.db (SQLite)
    ↓ drain every 100ms
Secondary Node:
  xnch audit ingest endpoint
    ↓ write to PostgreSQL audit table
This decouples decision latency from audit write latency. A slow disk write on the secondary never blocks a verdict on the primary.

5. Fallback Strategy if GPU is Unavailable
Two scenarios: primary GPU down (3090), secondary GPU down (1650).
Scenario A: RTX 3090 Unavailable
This is the critical path. The primary LLM cannot run.
Detection:
  vLLM health check fails: GET http://localhost:8000/health → timeout/error
  Nexi marks model layer status: DEGRADED

Immediate fallback sequence:

Step 1: Attempt CPU inference on primary node
  - llama.cpp CPU mode, same model
  - Performance: ~2–5 tokens/sec vs ~80–100 tokens/sec on 3090
  - Acceptable for low-urgency decisions, not for CRITICAL urgency
  - Enable if: task urgency != CRITICAL and queue depth < 3

Step 2: Attempt smaller model on secondary node 1650
  - Load Phi-3-mini Q4 if not already loaded
  - ~1.8GB fits in 4GB VRAM
  - Capability degradation: acceptable for QUERY intent, marginal for DECISION intent
  - Enable if: intent_class in [QUERY, LOW_COMPLEXITY_DECISION]

Step 3: Rule-based option generator (no model)
  - Nexi's Option Generator falls back to a deterministic rule engine
  - Generates options from a predefined action template library
  - Coverage: limited to known action types with prior episodes
  - No novel option generation
  - Enable if: target entity + intent class have ≥20 episodes in episodic memory

Step 4: Defer or escalate
  - If none of the above are viable, Nexi returns status: DEFERRED
  - xnch places the request in the hold queue
  - Operator is notified via CLI alert
  - System continues processing queued decisions when GPU recovers
Fallback state machine:
3090_OK → normal operation
3090_DOWN + urgency=LOW    → CPU inference (Step 1)
3090_DOWN + urgency=NORMAL → CPU inference or 1650 (Step 1 or 2)
3090_DOWN + urgency=HIGH   → 1650 or rule-based (Step 2 or 3)
3090_DOWN + urgency=CRITICAL → immediate escalation (Step 4), no degraded inference
Scenario B: GTX 1650 Unavailable
Lower impact. xnch has no GPU dependency. The 1650's only optional role is intent pre-classification.
Fallback: disable intent pre-classifier
  → Nexi handles full intent interpretation on i9 CPU
  → Latency impact: +50–100ms per session (acceptable)
  → No capability degradation, no functional change
xnch itself continues operating normally on i7 CPU. This scenario is effectively transparent to the system.

6. Scaling Path Without Breaking Current Design
The current design is built for single-node-pair operation. Every scaling step is additive — nothing in the base design needs to be torn out.
Scale Step 1: Add a second primary node (another machine with a capable GPU)
Current design already supports this because:

Nexi is stateless — it pins context at session start from xnch memory
Multiple Nexi instances can run in parallel, all calling the same xnch
Add a simple round-robin load balancer (nginx, HAProxy) in front of Nexi's port

Before:  Client → Nexi (primary.local)
After:   Client → HAProxy → Nexi (primary.local)
                           → Nexi (primary2.local)
Both Nexi instances call the same xnch on secondary.local
xnch becomes the bottleneck at this point, which leads to Step 2.
Scale Step 2: Replicate xnch memory reads (read replicas)
Write path stays on single xnch. Add PostgreSQL read replicas on additional nodes. Context Loader reads (which are the highest frequency) go to replicas. Verdict writes go to primary.
Nexi → POST /verdict          → xnch primary (secondary.local)
Nexi → POST /memory/read      → xnch read replica (secondary2.local)
No change to Nexi code — just configuration pointing read endpoints to replicas. xnch's API surface doesn't change.
Scale Step 3: Dedicated model node
When model inference throughput becomes the constraint, pull the model layer out of the primary node into a dedicated inference node. Nexi's Option Generator already calls the model via HTTP — change the endpoint URL in configuration.
Before: http://localhost:8000/v1/completions
After:  http://inference.local:8000/v1/completions
No Nexi code changes. No xnch changes. One config line.
Scale Step 4: Multiple model nodes with routing
Add a model router (LiteLLM or a simple custom router) that sits between Nexi and model backends. Routes by model name, load, and availability.
Nexi → model_router:9000 → inference1.local:8000 (Llama-3-13B)
                          → inference2.local:8000 (Mistral-7B)
                          → inference3.local:8000 (specialized model)
Again — Nexi's Option Generator changes one config value. The architectural contract (HTTP, OpenAI-compatible endpoint) was established at day one and held through all scaling steps.
What never changes regardless of scale:

xnch is the single write authority for governed memory
Every action goes through POST /verdict before execution
The audit trail schema is append-only and immutable
Nexi is stateless between sessions
The HTTP contract between nodes is the stable interface

The design scales by adding nodes behind stable interfaces, not by restructuring the architecture. The interfaces defined for a two-node system are the same interfaces a ten-node system uses.
