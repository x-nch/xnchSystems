# Final K8s Architecture — xnchSystems Homelab

## Cluster Overview

**K3s 2-node cluster**
- **i7 gate7** (localhost / 192.168.50.1) — Master + Control Plane + Memory Layer
- **i9 xnch-core** (192.168.1.9 / 192.168.50.2) — Worker + Inference + Always-on Services
- **Network:** Flannel overlay (10.42.0.0/16), isolated LAN (192.168.50.0/24)
- **Ingress:** Traefik v2 (built-in with K3s)
- **Storage:** K3s local-path provisioner (PVCs backed by host filesystem)

---

## i7 node (Master) — role=memory

### Workloads (xnch-system namespace)

| Pod | Image | Port | CPU | RAM | Type | Purpose |
|-----|-------|------|-----|-----|------|---------|
| **postgres-pgvector** | pgvector/pgvector:pg16 | 5432 | 2c | 5Gi | StatefulSet | XnchMemory layers 2-3 (episodic, relationship graph) |
| **redis** | redis:7-alpine | 6379 | 500m | 1Gi | Deployment | XnchMemory layer 0-1 (sensory, working memory) |
| **xnch-deployment** | xnch/xnch-server:latest | 8001 | 1c | 1.5Gi | Deployment | XNCH gateway (routing, orchestration) |
| **litellm-deployment** | ghcr.io/berriai/litellm:main | 4000 | 1c | 1Gi | Deployment | LLM router (Gemma4 local + Claude API) |
| **langfuse** | langfuse/langfuse:latest | 3000 | 1c | 1.5Gi | Deployment | Observability (LLM trace logging) |
| ~~agentmemory-deployment~~ | ~~node:20-slim~~ | ~~3111/3113~~ | ~~1c~~ | ~~2Gi~~ | ~~Deployment~~ | ~~CodeAgent memory — moved to bare metal~~ |
| **perception-daemonset** | xnch/perception:latest | 8002 | 1c | 3Gi | DaemonSet | Voice + Vision perception (GTX 1650 4GB) |

### Services (ClusterIP + NodePort)

| Service | ClusterIP | NodePort | Target | Use |
|---------|-----------|----------|--------|-----|
| xnch | 10.43.x.x | 30800 | xnch:8001 | Bare-metal OpenClaw on i7 |
| mem0 | 10.43.x.x | 30803 | mem0:8003 | Bare-metal services on i7 |
| postgres-pgvector | 10.43.x.x | — | postgres:5432 | Internal only (k8s pods) |
| redis | 10.43.x.x | — | redis:6379 | Internal only |
| litellm | 10.43.x.x | — | litellm:4000 | Internal LLM backend |
| langfuse | 10.43.x.x | — | langfuse:3000 | Internal observability |

### Storage (PVCs)

| PVC | Size | Mount | Pod | Type |
|-----|------|-------|-----|------|
| pgdata | 50Gi | /var/lib/postgresql/data | postgres-pgvector | StatefulSet template |
| xnch-data | 20Gi | /data | xnch | Deployment |
| xnch-vault | 100Gi | /vault | perception | DaemonSet |

### Ingress Routes (Traefik)

| Route | Host | Backend | Port | Use |
|-------|------|---------|------|-----|
| xnch-route | xnch.local | xnch | 8001 | XNCH gateway (primary entry) |
| litellm-route | llm.local | litellm | 4000 | LLM model router |
| langfuse-route | langfuse.local | langfuse | 3000 | Observability UI |
| nexi-route | nexi.local | nexi | 8000 | Nexi product engine (routed to i9) |

### Bare-Metal Services (outside K8s)

| Service | Process | Type | Port | Notes |
|---------|---------|------|------|-------|
| OpenClaw i7 | openclaw | systemd | 30800 (NodePort) | Always-on gateway (Telegram/WhatsApp) |
| agentmemory | agentmemory | systemd | 3111/3113 | MCP memory for Claude Code, OpenCode, OpenClaw |

---

## i9 node (Worker) — role=inference

### Workloads (xnch-system namespace)

| Pod | Image | Port | CPU | RAM | GPU | Type | Purpose |
|-----|-------|------|-----|-----|-----|------|---------|
| **nexi-deployment** | xnch/nexi-engine:latest | 8000 | 2c | 2Gi | — | Deployment | Character pipeline (intent → options → evaluate → dispatch) |
| **mem0-deployment** | mem0ai/mem0:latest | 8003 | 500m | 512Mi | — | Deployment | Memory middleware (connects to i7 postgres) |
| **zep-deployment** | ghcr.io/getzep/zep:latest | 8080 | 1c | 1Gi | — | Deployment | Conversation memory + entity extraction |

### Bare-Metal Services (on i9 host OS)

| Service | Process | Type | Port | Notes |
|---------|---------|------|------|-------|
| **gemma4-llama** | llama.cpp TurboQuant | systemd | 8080 | RTX 3090 inference (NOT containerized) |

### K8s Endpoints (route to bare-metal)

| Endpoint | Name | Target | Use |
|----------|------|--------|-----|
| vllm-gemma4 endpoints | vllm-gemma4 | 192.168.50.2:8080 | Nexi calls vllm-gemma4:8000 (K8s routes to systemd service) |

### Services (ClusterIP)

| Service | ClusterIP | Target | Use |
|---------|-----------|--------|-----|
| nexi | 10.43.x.x | nexi:8000 | Called by xnch on i7 (Flannel overlay) |
| mem0 | 10.43.x.x | mem0:8003 | Called by xnch/nexi (connects to i7 postgres) |
| zep | 10.43.x.x | zep:8080 | Called by nexi (entity extraction) |
| vllm-gemma4 (Endpoints) | 10.43.x.x | 192.168.50.2:8080 | Called by nexi (LLM inference) |

### Storage (PVCs)

None (no persistent storage needed on i9 — model is on host OS at `/home/x-nch/.cache/huggingface/hub`)

---

### Scheduled Jobs (xnch-system namespace)

| Job | Schedule | Node | Command | Purpose |
|-----|----------|------|---------|---------|
| consolidation-cronjob | 02:00 daily | i7 | `xnch.jobs.consolidation` | XnchMemory: summarize + graph extract + decay scores |
| agentmemory-bridge-cronjob | 02:30 daily | i7 | `xnch.jobs.agentmemory_bridge` | Extract XNCH-relevant facts from agentmemory → write to XnchMemory |
| vault-indexer-job | on-demand | i7 | `xnch.jobs.vault_indexer` | File watcher triggers: embed vault docs |

---

## Data Flow — Request Path

### Telegram Message → Response

```
User (Telegram)
    ↓
OpenClaw i7 (systemd bare-metal)
    ↓ POST http://localhost:30800/v1/chat/completions
XNCH gateway (i7 K8s pod :8001)
    ├─→ routing classifier (safety check)
    ├─→ mem0 (i9 K8s pod :8003) → queries postgres (i7)
    ├─→ relationship_store → always_inject context
    └─→ litellm (i7 K8s pod :4000)
        ├─→ Gemma4 (route to vllm-gemma4 K8s service → 192.168.50.2:8080)
        │   LLM inference (RTX 3090 on i9)
        └─→ Claude API (for judgment tasks)
    ↓
Nexi pipeline (i9 K8s pod :8000)
    ├─→ intent_interpreter
    ├─→ context_assembler (from XnchMemory 4 layers)
    ├─→ option_generator
    ├─→ evaluator
    └─→ dispatch → calls Gemma4 again
    ↓
XNCH post-processes
    ├─→ writes episode to pg_episodic_store
    ├─→ traces to langfuse
    └─→ updates memory decay scores
    ↓
Response returned to OpenClaw
    ↓
Telegram ← reply
```

### Mac CLI / Browser

```
macbook
  ├─→ SSH tunnel :8080 → i7:80 (Traefik)
  │   ├─→ xnch.local → xnch:8001
  │   ├─→ llm.local → litellm:4000
  │   ├─→ nexi.local → nexi:8000 (K8s routes to i9 via Flannel overlay)
  │   └─→ langfuse.local → langfuse:3000
  │
  ├─→ OpenClaw Mac (launchd) → http://i7:30800 (XNCH NodePort)
  │
  ├─→ Claude Code → agentmemory MCP → agentmemory (localhost:3111) [direct LAN]
  │
  └─→ OpenCode → agentmemory MCP → agentmemory (localhost:3111) [direct LAN]
```

---

## Memory Namespaces (AgentMemory)

| Namespace | Used by | Scope | Bridge |
|-----------|---------|-------|--------|
| `xnch-build` | Claude Code + OpenCode | Architecture decisions, code patterns | ← →  |
| `nexi-conversations` | OpenClaw Mac | Conversations with Nexi | nightly |
| `nexi-background` | OpenClaw i7 | Background tasks, proactivity | bridge |
| *agentmemory-bridge* | cronjob | Extracts XNCH-relevant facts | → XnchMemory |

---

## Known Issues & Workarounds (As-Built)

### DNS Cross-Node Issue
**Problem:** CoreDNS on i7 cannot forward UDP port 53 to i9 pods (Flannel overlay limitation).

**Workaround:** hostAliases in nexi deployment:
```yaml
hostAliases:
  - ip: "10.43.x.x"
    hostnames:
      - "postgres-pgvector"
      - "redis"
      - "litellm"
      - "xnch"
      - "mem0"
      - "langfuse"
```

### vLLM Containerization
**Problem:** Original plan had vllm-gemma4 as K8s pod. Model download issues + bare-metal llama.cpp better performance.

**Solution:** Removed vllm K8s pod. Instead:
- gemma4-llama.service runs on i9 host (systemd)
- K8s Endpoints object routes vllm-gemma4 service (10.43.x.x) to bare-metal 192.168.50.2:8080
- Pods call `vllm-gemma4:8000` — K8s DNS resolves to endpoint

### Zep Tiktoken Encoding Timeout
**Problem:** zep pod tries to download cl100k_base encoding from OpenAI CDN. i9 has no direct internet (isolated).

**Status:** Still broken. Needs:
- Option A: Pre-download encoding on i9, mount as volume
- Option B: Use zep with local embedding model (no tiktoken)

---

## Resource Budget Summary

### i7 Total Allocation

| Component | RAM | CPU | GPU |
|-----------|-----|-----|-----|
| K3s + system | 1Gi | 1c | — |
| postgres | 5Gi | 2c | — |
| redis | 1Gi | 500m | — |
| xnch | 1.5Gi | 1c | — |
| litellm | 1Gi | 1c | — |
| langfuse | 1.5Gi | 1c | — |
| perception | 3Gi | 1c | 4GB (GTX 1650) |
| **Total Used** | **16.5Gi** | **9c** | 4GB |
| **Available** | 15Gi | 12c | — |
| **Status** | ⚠️ Over | ✓ OK | ✓ Free |

**Note:** postgres + perception oversubscribed. In practice, postgres idles, perception runs on-demand.

### i9 Total Allocation

| Component | RAM | CPU | GPU |
|-----------|-----|-----|-----|
| K3s + system | 2Gi | 2c | — |
| nexi | 2Gi | 2c | — |
| mem0 | 512Mi | 500m | — |
| zep | 1Gi | 1c | — |
| gemma4-llama (bare-metal) | 20Gi | 4c | 18GB (RTX 3090) |
| **Total Used** | **25.5Gi** | **9.5c** | 18GB |
| **Available** | 46Gi | 24c | 24GB |
| **Status** | ✓ OK | ✓ OK | ✓ OK |

---

## Deployment Order (as applied)

```
Phase 0: Recon ✅
Phase 1: NAT + firewall ✅
Phase 2: K3s server on i7 ✅
Phase 3: K3s agent on i9 ✅
Phase 4: Node labels + NVIDIA plugin ✅
Phase 5: Fix vllm model path ✅ (skipped — using bare-metal instead)
Phase 6: Fill secrets + SCP manifests ✅
Phase 7: Apply manifests to cluster ✅
    - namespaces.yaml ✅
    - secrets-create.sh ✅ (with real values)
    - pvcs.yaml ✅
    - postgres-pgvector ✅ (StatefulSet running)
    - redis ✅
    - agentmemory ✅ (bare metal systemd on gate7 — migrated from K8s pod)
    - litellm ✅
    - xnch ✅ (fixed Docker image)
    - langfuse ✅
    - vllm-gemma4 ❌ (deleted — using bare-metal)
    - nexi ✅ (fixed Docker image)
    - mem0 ✅
    - zep ⚠️ (running but broken — tiktoken timeout)
    - ingress.yaml ✅ (Traefik routes)
    - jobs (cronjobs) ✅

Phase 8: OpenClaw systemd on i7 (PENDING)
Phase 9: Mac OpenClaw + agentmemory wiring (PENDING)
Phase 10: SSH tunnel + verification (PENDING)
```

---

## What's Ready Now

✅ K3s cluster (2-node, labeled)
✅ XNCH gateway (routing, memory retrieval)
✅ Nexi pipeline (character, intent → dispatch)
✅ Gemma4 inference (RTX 3090, 135 tok/s)
✅ Memory layers (Redis + PostgreSQL + Kuzu)
✅ Observation (Langfuse tracing)
✅ AgentMemory (bare metal on gate7 — Claude Code + OpenCode + OpenClaw memory)
✅ Ingress routing (Traefik)
✅ Scheduled jobs (consolidation + bridge)

⚠️ Zep (broken — tiktoken encoding)
❌ OpenClaw systemd on i7
❌ Mac OpenClaw CLI
❌ SSH tunnel config

---

## Next Steps

1. **Fix Zep:** Pre-download tiktoken encoding or use local embedder
2. **Test:** Send a message via Telegram, verify XnchMemory persistence, agentmemory capture
