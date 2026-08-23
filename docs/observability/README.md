# Observability

Two deliberately separate layers — keep them separate:

| Layer | Tool | Answers questions like |
|---|---|---|
| **Infra / security metrics** | Prometheus (this directory's configs) + app `/metrics` | How often, how fast, how full? Is the HITL gate being used? Is the GPU about to OOM? Did a memory tier stop working? |
| **LLM-semantic traces** | Langfuse (self-hosted v2) | *What* did the model decide and *why*? What did the prompt/completion look like? Which generation was slow and what did it cost? |

Full boundary rules: [`prometheus-vs-langfuse.md`](./prometheus-vs-langfuse.md)

## Current state (Phase A)

**Instrumented (in code):**
- `xnch` (:8001/metrics) — HTTP rate/latency per route template; HITL gate
  counters (`xnch_hitl_interrupts_opened_total`, `xnch_hitl_decisions_total`,
  `xnch_hitl_pending_interrupts`, oldest-pending age); consolidation job
  duration/success; SQLite store latency; deep memory-tier probes exported as
  gauges (`xnch_memory_tier_up{tier=redis|postgres|kuzu}`, probe seconds,
  last-success timestamp).
- Deep probes are real round-trips: Redis SET-with-TTL canary (+ sentinel key
  must never be immortal), Postgres episodic-table query latency, Kuzu
  write→read of a probe entity. JSON mirror at `GET /system/memory-tier-health`.
- `nexi` (:8000/metrics) — HTTP series; per-stage pipeline durations
  (`nexi_pipeline_stage_seconds{stage=interpret|load_context|...}`); pass
  outcomes; PolicyFilter option verdicts; goal-driver claim/step results;
  outcome-callback result rates.
- Both `/metrics` endpoints return **403 unless the client IP is in
  `*_METRICS_ALLOW_CIDRS`** (default localhost + 192.168.50.0/24).

**Deployment assets:** `infra/no-k3s/node-a/prometheus/` (scrape config),
prometheus service in Node A compose, `infra/no-k3s/exporters/`
(node_exporter ×2, dcgm-exporter on B, lock-holder via systemd collector).

**Verify after deploy:** `scripts/observability-smoke.sh`

## Phase B — alerting

13 rules in `infra/no-k3s/node-a/prometheus/rules/alerts.yml`, delivered by
Alertmanager (compose service on Node A :9093) to the default receiver:
**`POST /admin/alerts` on xnch** — every alert lands in the audit event log
(`events.jsonl`) and the operator UI surface (`GET /admin/alerts/recent`,
consumed by the dashboards). No credentials involved anywhere in that path.

For push notifications (ntfy/Telegram), copy a block from
`infra/no-k3s/node-a/alertmanager/receivers-extra.example.yml` into
`alertmanager.yml` **on the node** — topic names and bot tokens are
credentials; never commit them.

Severity model: `warning` (check within the day) · `critical` (act now) ·
`security` (bypass/abuse signals; group_wait 0s, repeats every 30m until resolved).

Validate rules after editing: 
`docker run --rm -v $PWD/infra/no-k3s/node-a/prometheus:/etc/prometheus prom/prometheus:v2.53.0 promtool check rules /etc/prometheus/rules/alerts.yml`

### HITL alerts
| Alert | Fires when | First move |
|---|---|---|
| `HitlInterruptPendingTooLong` (warn) | oldest pending interrupt >15m | open approvals view, decide |
| `HitlInterruptAbandoned` (critical) | >1h pending | decide explicitly or fix notification path |
| `HitlGateBypassFiring` (**security**) | any goal-loop EXECUTION allowed outside the gate (`xnch_hitl_gate_bypass_total`) | treat as incident: find the request via `HITL_GATE_BYPASS` events in `events.jsonl` (has `goal_id` + `request_id`); close the bypass or consciously accept it |
| `HitlQueueBacklog` (warn) | >5 pending for 10m | capacity problem — decide or raise thresholds |

### GPU alerts

| Alert | Fires when | First move |
|---|---|---|
| `VramHeadroomCritical` | VRAM >97% total for 5m | check lock holder (`node_systemd_unit_state`) — is Vision Media Stack holding memory next to Ornith's 0.95 reservation? |
| `GpuTemperatureHigh` | >83°C 5m | airflow/clocks; sustained heat throttles inference |
| `OrnithServiceDown` | unit inactive 3m | journalctl -u vllm-ornith; OOM after reload is the usual suspect |
| `GpuLockFlapping` | >3 state changes/30m | something restarts the media stack or Ornith repeatedly; every handoff = full model reload |

### Memory-tier alerts

| Alert | Fires when | Meaning |
|---|---|---|
| `MemoryTierProbeFailed` | deep probe down 2m (`xnch_memory_tier_up{tier}`) | functional failure the uptime checks can't see: Redis ignoring TTL, PG query failing, Kuzu write path broken |
| `MemoryTierProbeStale` | no successful probe in 5m | prober loop died even if tier looks fine |
| `ConsolidationFailing` | any consolidation failure in 24h | memory summarization/extraction/decay skipped |

### Infra meta

`CoreServiceUnreachable` (xnch/nexi scrape down 2m) and `ExporterDown`
(host/GPU exporters 5m) cover the monitoring plane itself.

## Phase C — dashboards (web/)

Three screens in the Next.js operator UI, under the sidebar's
**Observability** entry. The browser never talks to Prometheus directly:
xnch summarizes Prometheus server-side and the UI reads those JSON surfaces
through the same-origin `/api/gateway/*` proxy like every other screen.

| Screen | Route | xnch surface | Answers |
|---|---|---|---|
| System health | `/observability` | `GET /observability/summary` | Is anything down? Node A/B, GPU state, **lock holder** (Ornith vs Vision Media Stack), memory-tier probe results, firing alerts banner |
| HITL activity | `/observability/hitl` | `GET /observability/hitl?window_s&step_s` | Queue depth trend (6h), approve/reject rates (1h), time-to-decision distribution, prominent gate-bypass banner; links to the per-item approvals queue at `/` |
| Inference perf | `/observability/inference` | `GET /observability/inference?window_s&step_s` | Ornith tokens/s, e2e latency p50/p95, GPU util + VRAM trend with 97% threshold line, vLLM queue depth |

Backend pieces: `xnch/routes/observability.py` (surfaces) +
`xnch/observability/prom_summary.py` (thin Prometheus client). All queries
fail soft — when Prometheus is unreachable the endpoints return
`{"available": false}` plus whatever local signal still exists (tier probes,
pending-HITL snapshot), and the UI renders "metrics unavailable" instead of
lying. New scrape job added for vLLM native metrics (`vllm-node-b`).

Design system conformance: existing Card/HudCard/Badge primitives and tokens;
charts are hand-rolled SVG (`components/observability/charts.tsx`) — static
strokes only, so `prefers-reduced-motion` needs no special casing; accent is
used as data ink; text uses the established muted/foreground tokens (AA on
the near-black background). No new frontend dependencies.

Firefox: no Chromium-only APIs are used (no backdrop-filter, no 100vh hacks,
standard SVG); smoke-test the three routes in Firefox after deploy.

### Adding a chart/screen later

1. If the data doesn't exist yet: metric first ("Adding a new metric"), then a
   query in `routes/observability.py`.
2. Extend the matching TypeScript interface in `web/src/lib/api/observability.ts`
   and fetcher/hook in `observability-hooks.ts`.
3. Compose from the existing primitives in `web/src/components/observability/`;
   keep charts static-SVG and every color token-based.

## Adding a new alert

1. Add series instrumentation first if needed (see "Adding a new metric").
2. Append a rule to `rules/alerts.yml`: pick `severity` per the model above,
   set `area`, write `summary` + one-paragraph `description` + runbook anchor.
3. Add the anchor section to this README so the annotation link resolves.
4. Validate with the `promtool check rules` command above.

## Adding a new metric

1. Declare it next to its siblings in `xnch/observability/metrics.py` or
   `nexi/observability/metrics.py`. Prefix: `xnch_` / `nexi_`. Prefer
   counters for events, histograms for durations, gauges for levels.
2. Increment/observe it at the single place that owns that behavior (e.g.
   gate decisions live in `PipelineRuntime`, not in each route).
3. Write the failing test first: call the producer, then assert the series
   appears via `REGISTRY.collect()` (see
   `xnch/tests/test_xnch_observability_metrics.py::test_pipeline_invoke_and_resume_emit_hitl_metrics`).
4. If dashboards should show it, add the PromQL to the relevant screen spec in
   Phase C docs; if alerts depend on it, add the rule in Phase B.

## Non-goals

- No second LLM tracing system — anything "what did the model say/think"
  belongs in Langfuse spans/generations.
- No plaintext credentials in scrape configs or exporter units, ever.
