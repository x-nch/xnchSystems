# Prometheus vs. Langfuse — the boundary

One rule of thumb: **Prometheus answers "how much / how often / how healthy";
Langfuse answers "what and why".**

If removing the system would leave you unable to notice a *condition*, it is a
metric. If you would only miss the *explanation*, it is a trace.

## Prometheus owns (this repo's `/metrics` + exporters)

- Rates: HTTP requests per route, HITL interrupts opened, approve/reject rate,
  policy-filter blocks, goal-driver claim outcomes, callback outcomes.
- Latencies: per-route request duration, per-pipeline-stage duration,
  consolidation run duration, SQLite store queries, deep-probe round-trips.
- Levels & gauges: pending-HITL count and oldest-pending age, approval queue
  depth by status (once the `approvals` table exists), VRAM used vs budget,
  GPU util/temp, memory-tier up/down, Redis canary TTL state, Kuzu probe age.
- Existence/health: node_exporter unit states (Ornith vs Vision lock holder),
  container/unit liveness, scrape target up/down.

## Langfuse owns

- The content of an LLM call: prompt, completion, model, token usage.
- Agent-run narratives: which options the model generated for a decision and
  the stated rationale; reflection/consolidation summaries.
- Cost attribution per generation.
- LLM-level spans (`voice.stt`, `voice.tts`) when voice tracing lands.

## Anti-patterns this boundary forbids

1. **Re-implementing traces as metrics** — do not add "prompt length" or
   "which model answered" labels to counters; cardinality explodes and the
   answer already lives in Langfuse.
2. **Using Langfuse as an alert source for infra conditions** — a missing
   trace is not a health signal; if something must page the operator, it needs
   a metric and a rule (Phase B).
3. **Duplicating gate decisions in both systems' semantics** — metrics record
   *that* an interrupt was approved/rejected; Langfuse may additionally show
   *what proposal* was being approved via spans on the same trace_id.

## Join key

Both layers carry `trace_id`. xnch emits it into EventLog entries and pipeline
state; pass it to Langfuse as `trace_id` in `trace_llm_call`. Correlate a
metric anomaly to its semantic explanation by that id.

## When adding anything new, ask

> Would I page a human on this? → metric (+ Phase B rule).
> Would I read this to debug *why* it fired? → Langfuse span/generation.
