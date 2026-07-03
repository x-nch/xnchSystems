# Request Flow — Live Cluster 2026-06-28

## Test: POST /nexi/chat

**Attempted request:**
```bash
curl -X POST http://10.42.1.63:8000/nexi/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Actor-Role: openclaw' \
  -d '{"session_id":"review-test-001","message":"what is your current memory state"}'
```

**Result: TIMEOUT (>30 seconds, no response)**

This indicates nexi's /nexi/chat endpoint is either:
1. Not served (missing route)
2. Hanging on an internal dependency
3. Requires additional parameters/headers

---

## Expected Request Flow (from architecture)

### Path: External → xnch → nexi → litellm → llama-server

```
1. External client
   ↓ HTTP POST :8000/nexi/chat (or :30800 NodePort → xnch:8001)
2. xnch-server (gate7, 10.42.0.33:8001)
   ↓ Authenticates, validates, routes to nexi
   ↓ HTTP POST nexi:8000/nexi/chat
3. nexi-engine (xnch-core, 10.42.1.63:8000)  ← CROSS-NODE VXLAN
   ↓ Interprets intent, selects policy
   ↓ Calls litellm for LLM inference
   ↓ HTTP POST litellm:4000/chat/completions
4. litellm (gate7, 10.42.0.44:4000)  ← CROSS-NODE VXLAN
   ↓ Routes to configured model endpoint
   ↓ HTTP POST vllm-gemma4:8000/v1/completions
5. llama-server (xnch-core host, 192.168.50.2:8080)  ← via no-selector Service
   ↓ Runs inference on Gemma 4 26B Q4_K_M on RTX 3090
   ↓ Returns tokens
   [Path reverses back to caller]
```

### Data Store Hits (during typical request)

| Store | Purpose | Reads | Writes |
|-------|---------|-------|--------|
| **PostgreSQL** | Langfuse traces, LiteLLM config, session state | Session lookup, model config | Trace logging, spend logs |
| **Redis** | LiteLLM caching, rate limiting | Cache lookups | Cache writes |
| **agentmemory** (new) | Agent memory store | Context retrieval | Memory updates |
| **mem0** | Long-term memory | Semantic search | New memories |

---

## Live Observations

### What was confirmed running:
| Service | Status | Address | Responded to health check? |
|---------|--------|---------|--------------------------|
| **xnch-server** | Running | 10.42.0.33:8001 | Not tested directly |
| **nexi-engine** | Running | 10.42.1.63:8000 | No response to /nexi/chat (timeout) |
| **litellm** | Running | 10.42.0.44:4000 | curl from outside failed (timeout) |
| **llama-server** | Running | 192.168.50.2:8080 | ✅ health=ok, inference works |
| **postgres** | Running | 10.42.0.31:5432 | ✅ queryable (105 tables) |
| **redis** | Running | 10.42.0.29:6379 | ✅ PONG |
| **langfuse** | Running | 10.42.0.43:3000 | Not tested |
| **agentmemory** | Running | 10.42.0.49:3111 | Not tested |
| **mem0** | Running | 10.42.1.40:8003 | Not tested |
| **zep** | **CrashLoopBackOff** | 10.42.1.49:8080 | ❌ Unavailable (store.type not set) |

### Cross-node traffic pattern:
- xnch-core (nexi, mem0) → gate7 (litellm, postgres, redis, langfuse) uses VXLAN overlay
- gate7 (litellm) → xnch-core host (llama-server) uses Service no-selector Endpoint (192.168.50.2:8080)

### Inference Timings (direct to llama-server):
```
Prompt: 1 token → 51.3ms (19.5 tok/s)
Prediction: 10 tokens → 102.6ms (97.4 tok/s)
```
Total: ~154ms for a simple prompt-completion cycle on llama-server.

---

## Active Connections (observed during inspection)

No established TCP connections were found from inside the pods (xnch, nexi, litellm), confirming **there is no active traffic** — the cluster is idle/at rest.

Redis stats confirm minimal usage:
- Total connections received: 5
- Total commands processed: 45
- Keyspace hits: 9, misses: 2
- Current keys: 0

---

## Critical Issues

1. **Nexi /nexi/chat endpoint is unresponsive** — the test request timed out at 30s. This could be because:
   - The URL path is not `/nexi/chat` (might be `/chat` or different)
   - Nexi is waiting on a dependency (mem0, zep, agentmemory) that isn't responding
   - The server startup completed but the route wasn't registered
   - Wrong target (maybe request goes via xnch first at port 8001:30800)

2. **zep is down** — if nexi depends on zep for memory, the timeout could be caused by nexi waiting for an unavailable zep connection.

3. **No Ingress routes defined** — traefik is running but no Ingress resource routes traffic anywhere.

4. **Consolidation cronjob has never run** — `lastScheduleTime` and `lastSuccessfulTime` are both null, age 5h.

5. **All images use `:latest` tag** — no immutability; rollbacks will be unreliable.
