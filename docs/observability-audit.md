# Observability Audit — xnchSystems (Node A + Node B)

**Date:** 2026-08-23
**Scope:** Live `infra/no-k3s/` deployment. Node A = gate7 / i7 / 192.168.50.1 (control plane). Node B = xnch-core / i9 / 192.168.50.2 (GPU inference).
**Method:** Repo-only evidence — compose files, systemd units, and source at submodule commits `xnch@f81693e1`, `nexi@6f321ee0`. Runtime env files (`~/.xnch/*.env`) live on the nodes and were not inspected; items depending on them are listed under "Verify on the nodes" below.

> Note: `infra/k8s/` is the legacy layout (unpinned `langfuse:latest`, old node names) — superseded by `no-k3s/` per `infra/no-k3s/MIGRATION.md`. Findings below apply to the live no-k3s stack only.

---

## 1. What exists today, per layer

### 1.1 LLM-level tracing — Langfuse (partial)

| Component | State |
|---|---|
| Langfuse server | Self-hosted v2 on Node A :3000 with dedicated Postgres (:5433), container healthcheck (`infra/no-k3s/node-a/docker-compose.yml:25-46`). Pinned to v2 deliberately to avoid v3's ClickHouse requirement (`MIGRATION.md:91-96`). |
| Instrumentation | Hand-rolled client: `xnch/observability/langfuse_client.py` — a single `trace_llm_call()` posting `generation-create` events via async httpx. No span/trace-tree API. |
| Call sites | Exactly four: `xnch/routes/verdict.py:69,118`, `nexi/adapters/model_adapter.py:191,223`. Voice spans (`voice.stt`, `voice.tts`) and Prometheus voice counters listed in `docs/guides/nexi-voice-architecture.md:418-427` are **not implemented**. |
| LiteLLM | Proxy on Node A :4000 routes Ornith traffic but has **no callbacks configured** (`infra/no-k3s/node-a/litellm-config/config.yaml` has only model_list + router_settings) → zero LLM traces and zero metrics from LiteLLM itself. |
| Failure mode | `except Exception: return None` (`langfuse_client.py:74-75`) — if Langfuse or its Postgres dies, traces are dropped **silently**, forever. |
| Known debt | Token usage counted as whitespace-split words, not tokens (`langfuse_client.py:58-60`; flagged in `misc/review_report.md`). |

### 1.2 Infra metrics / alerting — absent

- **No Prometheus, Grafana, Alertmanager, node_exporter, cAdvisor, DCGM exporter, Loki/Promtail anywhere in the repo** (glob across all manifests: zero matches).
- References to "existing Prometheus" in `misc/rearchitecture-discussion.md` reflect prior experience/plans, **not anything deployed here**.
- Docker healthchecks exist for all six containers (liveness only), but nothing consumes their state — `docker ps` is the only consumer.
- App health endpoints:
  - `xnch GET /health` (`xnch/main.py:219-228`) — Redis ping + state_version **only**; does not check Postgres, Kuzu, or vLLM.
  - `nexi GET /health` (`nexi/main.py:266-268`) — returns static `{"status":"ok"}`; checks nothing.
  - vLLM `/health` — real dependency check; consumed by boot scripts and the on-demand `GET /system/llm-status` probe (`xnch/main.py:238-254`).
- Pull-only tooling: `xnch_health` MCP tool (service health + Redis connectivity + bridge/web-search blocks) and `infra/no-k3s/e2e-test.sh` (post-deploy validation). Both require a human.

### 1.3 GPU observability on Node B — absent

- `nvidia-smi` is used **only as a boot preflight** (`start-node-b.sh:92`). No DCGM exporter, no thermal logging, no VRAM time-series.
- Deployed budget is `--gpu-memory-utilization 0.95` (`vllm-ornith.service:23`) — **not 0.92** as commonly cited. At 95% reservation with `--max-model-len 32768`, prefix caching, and `max-num-seqs 2`, steady-state headroom is ~5% of VRAM; activation spikes or fragmentation can OOM the process (systemd restarts it after 15 s, silently losing in-flight generations).
- The Vision Media Stack does not appear anywhere in this repo (no manifests, no systemd units). Its exclusivity constraint with Ornith is **not codified**: no systemd `Conflicts=`/ordering, no device-cgroup isolation, no pre-start guard. If a media/vision GPU workload is ever started on Node B, nothing prevents VRAM contention besides luck.

### 1.4 Service/process health

| Service | Node | Liveness | Depth |
|---|---|---|---|
| litellm, langfuse, redis, postgres-pgvector, langfuse-postgres, searxng | A | Docker healthcheck | Process-up only; unconsumed |
| xnch (:8001), perception (:8002), vault-indexer, consolidation.timer, tailscale-funnel | A | systemd `Restart=on-failure` | Restart loops invisible |
| vllm-ornith (:8082), nexi (:8000), fs-read-agent, exec-agent | B | systemd | Same |

### 1.5 Audit trail (adjacent, worth noting)

- `EventLog` → append-only JSONL (`~/.xnch/audit/events.jsonl`, `xnch/audit/event_log.py`) plus `DecisionLedger`. Emits on session, verdict allow/block, injection scans, policy, execution, memory writes, startup/shutdown — fire-and-forget with `except Exception: pass`.
- **No rotation** (unbounded growth) and **silent write loss** on disk-full.
- Consolidation job runs via timer → `curl -sf POST :8001/admin/consolidate` (`consolidation.service:9`); failure surfaces only as journald noise / failed unit.

---

## 2. Gap table

| # | Layer | Current coverage | Gap | Suggested fix |
|---|---|---|---|---|
| G1 | **HITL gate** | Nothing. `/governance/pipeline/invoke\|resume\|{thread}` (`xnch/routes/pipeline.py`) and `PipelineRuntime` emit no events, no metrics, no traces; contrast session/policy/memory routes which do `event_log.emit` | The most security-relevant path in the system has **zero durable signal** outside the LangGraph checkpointer tables; approve/reject/interrupt are unobservable; **no timeout mechanism exists at all** — a pending interrupt waits forever | Add `event_log.emit` at interrupt/approve/reject/resume-not-found; add Prometheus counters `xnch_hitl_interrupts_total{decision}`, gauge `xnch_hitl_pending_age_seconds`; implement a stale-interrupt sweeper (configurable TTL) that expires and alerts |
| G2 | Infra metrics | None | No metrics/alerting stack at all; "is the system healthy" = manual curl/docker ps/journalctl | Add Prometheus + Grafana (+ Alertmanager) to Node A compose; node_exporter on both hosts; blackbox-exporter probing all `/health` endpoints |
| G3 | GPU (Node B) | Boot-time nvidia-smi only | No VRAM/util/temp/power history; can't correlate OOM restarts with load; exclusivity vs media stack unenforced/unobserved | dcgm-exporter on Node B; alert VRAM > 97%, temp > 83 °C, throttle-active; document/enforce Ornith↔media-stack mutual exclusion (systemd `Conflicts=` or a preflight guard) |
| G4 | Trace coverage | 4 hand-wired call sites | LiteLLM-proxied calls, intent interpretation, consolidation summarization, voice STT/TTS untraced; trace loss silent | Enable LiteLLM `success_callback`/`failure_callback: [langfuse]` + LiteLLM's own Prometheus metrics; extend `LangfuseClient` with spans; add a `langfuse_trace_failures_total` counter instead of silent drop |
| G5 | Health endpoint depth | xnch checks Redis only; nexi checks nothing | Postgres/Kuzu/vLLM failures don't surface in any health probe; nexi reports healthy while dead downstream | Deepen both `/health`s (dependency pings, `degraded` semantics); keep them cheap and alert on them |
| G6 | Memory tier | TTLs set in code (sessions 3600 s/86400 s, sensory 60 s, kv sessions configurable); Kuzu `get_stats()` pull endpoint | No hit/miss, eviction, keys-per-tier, pgvector query latency, graph size trend; Redis memory pressure invisible until crash | Export redis_exporter + postgres_exporter; scrape `redis_info_*`, `pg_stat_statements` p95, scheduled Kuzu stats scrape via existing `/memory/graph/stats` route |
| G7 | SPOF: postgres-pgvector | Single instance; backs episodic store, relationship store, **HITL checkpointer**, scraper store; no backup automation visible; no connection/saturation monitoring | Dies → xnch degraded, pending HITL approvals unreadable, consolidation fails — silently | postgres_exporter + page-level alert on down; nightly `pg_dump`/WAL archive with backup-age alert |
| G8 | SPOF: Redis | Single instance; working memory, sensory buffer, rate limits, idempotency cache; xnch `/health` degrades but nobody watches | Crash = silent context amnesia + broken rate limiting while endpoints still answer | Alert on `redis_down`/`degraded` from `/health`; consider AOF persistence (volume exists; policy unstated) |
| G9 | SPOF: langfuse-postgres + silent trace drop | Dedicated instance; client swallows all errors | Double-silent failure: tracing stops with zero signal (G4 fix covers detection) | Same counter-based alert; add langfuse-postgres to backup rotation |
| G10 | Logs/audit durability | Local JSONL, no rotation, swallow-on-error; journalctl per unit | Disk-full kills audit trail silently; logs die with host | Logrotate for `events.jsonl`/`decisions.jsonl`; ship journals (promtail/alloy or rsync) off-node; alert on write-failure and disk > 85% |
| G11 | Config drift | HITL gate is opt-in (`XNCH_LANGGRAPH_PIPELINE=true`), modes `always/risk_threshold/never` (`xnch/config.py:129-132`); production env not visible in repo | If the flag is off in prod, EXECUTION decisions take the nexi default path **without any gate**; `mode=never` would silently disable the gate too | Verify prod env; export current `hitl_execution_mode` as a metric/label so drift is visible on the dashboard |
| G12 | Watchdog of the watchdog | Everything self-hosted on two hosts | If Node A dies entirely, no external monitor notices (Tailscale funnel also dies) | Cheap external uptime probe (e.g., hosted ping/healthcheck service hitting the funnel URL) |

---

## 3. Proposed dashboards (minimal set, one Grafana instance on Node A)

Priority order = top-to-bottom reading order for a 5-minute "is the system healthy" check.

### D1 — System health (first thing you see)
| Panel | Type | Source |
|---|---|---|
| Node A / Node B up | Stat | blackbox probe `:8001/health`, `:8000/health` |
| Containers healthy (6) | Stat/table | `docker_container_health` via cAdvisor or compose healthcheck exporter |
| systemd units active (xnch, perception, consolidation.timer / vllm-ornith, nexi) | Table | node_exporter systemd collector |
| vLLM reachable + probe latency | Stat | reuse `/system/llm-status` probe as recurring blackbox check |
| Disk % (both nodes), audit JSONL growth | Time series | node_exporter |

### D2 — HITL gate activity (security row)
| Panel | Type | Source |
|---|---|---|
| Pending interrupts + **age of oldest pending** | Stat (red > 15 min) | new gauge (G1) |
| Interrupts opened, approved, rejected (rate + ratio) | Time series | new counters (G1) |
| Active `hitl_execution_mode` | Stat | exported setting (G11) |
| Stale-expired interrupts | Counter | sweeper (G1) |

### D3 — Inference
| Panel | Type | Source |
|---|---|---|
| TTFT p50/p95, inter-token latency, tokens/sec | Time series | vLLM metrics via dcgm/prometheus plugin or LiteLLM metrics |
| Queue depth (running/waiting), KV-cache utilization % | Gauge | vLLM metrics |
| VRAM used vs `gpu-memory-utilization` budget line | Time series | dcgm-exporter |
| LiteLLM upstream failures/retries | Counter | LiteLLM Prometheus callback (G4) |

### D4 — Memory tier
| Panel | Type | Source |
|---|---|---|
| Redis: memory, keyspace hit/miss, evicted/expired per sec, `session:*` count | Time series | redis_exporter (G6/G8) |
| Postgres: active conns, p95 query latency, DB/pgvector index size | Time series | postgres_exporter (G6/G7) |
| Kuzu: entity/relation counts trend, graph.kuzu disk size | Time series | scheduled scrape of existing stats route (G6) |
| Langfuse ingestion success/failure | Counter | app-side counter (G4/G9) |

### D5 — GPU hardware (Node B)
VRAM used/headroom · util % · temp · power · throttle reasons · ECC errors (dcgm-exporter).

---

## 4. Minimum alert set

| Alert | Threshold | Severity |
|---|---|---|
| Pending HITL interrupt age | > 15 min warn / > 1 h critical | High — this is an unattended execution waiting on a human |
| HITL reject spike | > 3× baseline in 1 h | High — possible misbehavior upstream of the gate |
| postgres-pgvector down / backup age > 24 h | immediate | Page |
| Redis down or `/health` degraded > 2 min | immediate | Page |
| Any container unhealthy > 5 min; systemd unit flapping | — | Warn |
| vLLM down > 5 min; GPU temp > 83 °C; VRAM headroom < 3% | — | High |
| `hitl_execution_mode != always` (unexpected) | — | High |
| Langfuse trace failures > 0 sustained 10 min | — | Warn |
| Disk > 85%; events.jsonl write failure; consolidation last-success > 24 h | — | Warn |

---

## 5. Quick wins (ordered)

1. Wire `event_log.emit` into pipeline invoke/interrupt/resume + add stale-interrupt sweeper (G1) — pure code, no new infra.
2. Add Prometheus + Grafana + node_exporter ×2 + blackbox-exporter to Node A compose; import D1/D2 empty-state dashboards (G2).
3. dcgm-exporter on Node B (G3).
4. Enable LiteLLM langfuse + prometheus callbacks — biggest trace/metric coverage jump for a config change (G4).
5. Deepen both `/health` endpoints (G5).
6. Add redis/postgres exporters + minimum alert rules §4 (G6–G8).
7. External uptime probe on the Tailscale funnel URL (G12).

## 6. Verify on the nodes (not visible from repo)

- Is `XNCH_LANGGRAPH_PIPELINE=true` set in `~/.xnch/xnch.env`? (If not, production EXECUTION bypasses the HITL gate entirely — see G11.)
- Are `XNCH_LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` set to the self-hosted instance? (Defaults point to cloud.langfuse.com with empty creds = tracing disabled.)
- Reconcile the GPU budget story: deployed value is **0.95** (`vllm-ornith.service:23`); confirm intended value before sizing alerts around headroom.
- Confirm whether the Vision Media Stack actually shares Node B today; if yes, its VRAM footprint must be subtracted from the budget math and mutually excluded from vLLM.
