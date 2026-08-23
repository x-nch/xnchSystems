# ADR: Local Training Subsystem (`xnch-train`)

- **Status:** Proposed
- **Date:** 2026-08-22
- **Scope:** Capability to improve the locally-served model (Ornith-1.0-35B) from real usage signal, on the existing single RTX3090, without violating local-first, HITL-gate, zero-team, or no-heavy-deps principles.
- **Follow-up:** Implementation sessions execute against this doc phase by phase. No code in this ADR.

---

## Context

The system currently serves frozen weights forever. Meanwhile it *already generates* high-value training signal and throws it away:

- **Langfuse traces** over all four memory tiers (agent traces, tool-call outcomes, disagreement-protocol triggers).
- **HITL approve/reject decisions** on the `propose → interrupt → execute` gate — preference data produced for free, currently unused.
- **Corrected outputs** landing in episodic memory (Postgres+pgvector).
- **Execution outcomes** (`SUCCESS / PARTIAL / FAILURE`) persisted by `xnch/routes/execution.py::execution_outcome`.

Constraints that shape every decision below:

| Constraint | Implication |
|---|---|
| One RTX3090 (24 GB), already at 0.92–0.95 `gpu-memory-utilization` serving Ornith GPTQ (`vllm-ornith.service`: `gptq_marlin`, `max-model-len 32768`, `max-num-seqs 2`) | Any training is a **third contender for the same GPU**, behind the existing `Conflicts=` exclusivity between Ornith and the Vision Media Stack |
| Ornith *is* the inference backend for Nexi (port 8082) | Stopping vLLM for training = a deliberate, whole-system outage — must be an approved event, not a side effect |
| Local-first with opt-in cloud escape hatch (Claude via LiteLLM, audited, never default) | Same pattern applies to any hypothetical cloud-GPU training: opt-in only |
| HITL gate is security-critical; weight swaps are live-system actions | Checkpoint promotion **must** ride the existing propose→interrupt→execute path |
| Solo operator, zero babysitting | Every job must survive being started and left alone; failures must fail safe and leave the GPU free |
| No new heavy deps without justification | Torch/PEFT/TRL live in an **isolated venv on Node B**, never in xnch/nexi dependency trees |

Relevant existing infrastructure this plan reuses rather than reinvents:

- **Goal model** (`docs/superpowers/plans/2026-08-17-goal-tracking-loop.md`): `GoalStore` (xnch/SQLite), `claim_next_goal` lease semantics, `GoalStatus` enum, `/goals` routes, gated driver loop (`NEXI_GOAL_DRIVER_ENABLED` precedent).
- **PolicyFilter + verdict flow**: the shared HITL path across LangGraph-primary and beeAI-PoC orchestration.
- **systemd exclusivity regime** on Node B (`infra/no-k3s/node-b/systemd/`).
- **Langfuse** as the single observability sink.

---

## Decision

**Adopt a memory-first, adapter-only, two-window, fully-gated training subsystem:**

1. **The four-tier memory remains the primary adaptation mechanism.** Weight training exists only for the residual: systematic patterns memory cannot carry (persona calibration, recurring tool-call formatting discipline, stable behavioral corrections).
2. **Primary training method: QLoRA (NF4 base, LoRA adapters, attention-modules-first), staged SFT → DPO.** Full fine-tune ruled out. Adapters are merged into the fp16 base, requantized to GPTQ, and promoted as a *new immutable checkpoint* — not served as hot-swapped vLLM LoRAs.
3. **Two exclusive GPU windows per cycle:** a long *Train Window* (extract→scrub→train→merge→requant→eval→bench, holding the GPU lock) and a short *Promote Window* (symlink flip + vLLM restart + smoke test, HITL-approved separately).
4. **Training cycles are Goals.** `xnch-train` is a new top-level submodule that creates and claims Goals through the existing xnch GoalStore; the final pipeline step emits a promotion *proposal* through the standard HITL verdict path.
5. **Training joins the systemd `Conflicts=` group** as a peer of `vllm-ornith.service` and the Vision Media Stack — never bypasses it.

### 1. Data Pipeline

**Sources already captured — extraction with zero new instrumentation:**

| Signal | Lives in | Extraction |
|---|---|---|
| Agent traces, spans, generations | Langfuse (Node A) | Paginated `fetch_traces` / `fetch_observations` via Python SDK → JSONL |
| HITL approve/reject verdicts | xnch episodes (verdict flow persists `context_snapshot` incl. verdict) | SQL extract from Postgres episodes filtered to decision records: `action_spec`, `verdict ∈ {APPROVE, BLOCK, MODIFY}`, context |
| Corrected outputs | Postgres+pgvector episodic tier | SQL extract of episodes flagged as corrections (see instrumentation below for linkage) |
| Disagreement-protocol triggers | Langfuse + episodes | Same two extractors, filtered by protocol marker |
| Tool-call outcomes | `execution_outcome` episodes (`outcome_status`) | SQL extract keyed on `decision_id` |

Extractor output is one canonical record shape: `{trace_id, ts, source, input_context, output, outcome, verdict, scrub_status}` written to a dataset directory on Node A, then rsynced to Node B at Train Window start.

**Minimal new instrumentation (three additive fields, nothing structural):**
1. `rejection_reason` (small enum + free-text) on HITL verdicts — turns rejects from noise into labels.
2. `modified_action_spec` alongside original when a human approves-after-editing — the highest-value preference pair in the system (chosen = modified, rejected = original).
3. `corrects_decision_id` linkage on correction episodes — converts scattered corrections into supervised pairs.

**PII/secrets hygiene (hard requirement — payment-infra-adjacent context):**
- A **scrubbing stage runs on Node A, before anything touches a dataset file**. Nothing leaves the memory tier raw.
- Layers: secret-pattern denylist (API keys, tokens, card-shaped numbers w/ Luhn check, credentials), entity pseudonymization (HMAC-with-local-key so format survives training), and a field blocklist (raw payloads never exported).
- Every dataset ships with a `scrub_manifest` (pattern-set version, per-rule redaction counts, operator sign-off hash). A dataset without a manifest is invalid input to any trainer.
- **Checkpoints are treated as derived secrets**: they can memorize. Export/share of any checkpoint or adapter is itself a security-sensitive action requiring the HITL gate + scrub-manifest audit trail (principle c).

### 2. Training Method Selection

| Method | Verdict | Why |
|---|---|---|
| **Full fine-tune** | ❌ Rejected | Optimizer states span *all* ~30–35B params (MoE router + every expert receives gradients as data routes through them): fp16 weights + fp32 master + Adam m/v ≫ 24 GB even with offloading. Also evicts production serving for days. Non-starter on this hardware. |
| **Cloud GPU fine-tune** | ❌ Rejected (for now) | Violates local-first default. May return later as an explicit, audited, **opt-in** escape hatch (identical pattern to Claude-via-LiteLLM), never silent. |
| **Prompt/RAG-only (memory as sole adaptation)** | ⚠️ Adopted as *baseline*, not endpoint | Already works for factual/contextual adaptation. Kept as the control arm: Phases 0–2 measure adapter-vs-memory on identical eval sets. If memory wins on the residual, training stops. Honest default until proven otherwise. |
| **ORPO** | ❌ Rejected | Single-stage elegance is real, but TRL/MoE maturity trails DPO, and coupling SFT+preference tradeoffs into one ratio removes the solo operator's ability to debug stages independently. Revisit if pair volume stays tiny. |
| **Hot-served vLLM LoRA (no merge)** | ❌ Rejected (primary path) | Production serves `gptq_marlin`; LoRA-over-GPTQ-marlin support in vLLM is incomplete/version-sensitive (Open Question Q1). Merge→requant is version-proof. Revisit if Q1 verifies support. |
| **QLoRA SFT → DPO (adapters on NF4 base, merged + requantized)** | ✅ **Primary** | See budget below. |

**Realistic budgets on the RTX3090 (24 GB), Qwen3-MoE-class base (~3B active params):**

- Base in NF4 ≈ 16–18 GB. Add LoRA adapters (attention modules first, r=16–32), gradient checkpointing, `paged_adamw`, bs=1, seq ≤ 2048 → **≈ 21–23 GB peak. Fits, barely; expect OOM-tuning cycles during Phase 1.** Expand adapters toward MLP/gate projections only if eval demands it.
- DPO memory is the same order: with LoRA, the reference model is the *same* frozen base with adapters disabled — no second weight copy.
- Wall-clock: a typical cycle (≈2k samples × ≤1k tokens) trains in **1–3 h end-to-end including base load, adapter merge, and eval**; the GPTQ requant pass adds **1–2 h**. A single evening window is comfortably sufficient — scheduling pressure is low.

**Scheduling (no second GPU, no babysitter):**
- Phase 1–2: **explicit manual trigger only** — `systemctl start xtrain-cycle@<run>.service`, which is itself preceded by an approved Goal. No timers.
- Phase 3 (opt-in automation): trigger proposes a training Goal only when (GPU idle by Ornith's own absence *or* an approved maintenance window) ∧ (enough new scrubbed data since last cycle). Automation proposes; it never starts the GPU takeover or promotion by itself.
- Optional pairing (explicit decision per window): enabling the LiteLLM Claude opt-in route during a Train Window keeps the agent alive during the sanctioned outage — audited, announced, never default.

### 3. Eval & Safety Gate

**"Better" is five concrete numbers vs. the incumbent checkpoint, measured by the same harness version (suites are version-stamped; incumbent re-scored whenever the suite bumps):**

1. **Action fidelity** — replay held-out *real* traces as static prompts (no live tools); score action-type match + argument-F1 against the recorded approved `action_spec`.
2. **Rejection-avoidance** — replay contexts of historically BLOCKED proposals; rule/rubric check whether the candidate repeats the rejecting behavior.
3. **Persona consistency** — fixed Nexi voice probe battery (~50 prompts), rule/classifier-scored.
4. **Tool-call validity** — `%` of outputs parsing cleanly under `qwen3_xml` on a synthetic agentic set.
5. **Serving regression** — post-requant vLLM bench on a fixed prompt set: TTFT/p95 within +10% of incumbent (adapters/checkpoint changes can silently cost latency).

**Automated gate (blocking, inside the Train Window, before the GPU lock is released):** candidate is *eligible* iff (1)(3)(4) ≥ incumbent − ε, no metric regresses > agreed bound, and (5) passes. Fail → report to Langfuse, candidate archived, no proposal emitted. Temporal train/eval split is mandatory (eval set drawn strictly *after* the training cutoff date) to prevent contamination inflation.

**Human gate (mandatory, separate, explicit — principle c):** eligible ≠ deployed. Eligibility causes `xnch-train` to emit a **promotion proposal through the standard pipeline** (PolicyFilter → interrupt → verdict). Approval triggers the Promote Window: flip `current` symlink → restart `vllm-ornith.service` → scripted smoke eval → Langfuse `promotion` event. Rollback is one command (previous release symlink retained) and emits a `rollback` event. Weight swaps are never auto-applied; Phase 3 automates only the *proposal*, never the swap.

### 4. System Integration

**Placement: new top-level submodule `xnch-train`.**

Rejected alternatives:
- *Under xnch*: wrong deploy target (xnch lives on Node A; training code, its torch venv, and datasets belong on Node B) and pollutes the control-plane dependency tree.
- *Folded into nexi*: nexi is the request-path engine; a training crash-loop must never be able to degrade the decision pipeline. Different release cadence, different risk profile.
- *Existing workstream*: no current workstream owns "improve the weights"; bolting it on blurs ownership.

Justification: `xnch-train` is symmetric to nexi — a Node-B-resident worker consuming xnch's REST/Goal/HITL surfaces through a narrow client, with its own pinned venv (torch/peft/trl — the explicit heavy-dep justification: no lighter toolchain performs MoE QLoRA; it never leaks into xnch/nexi deps) and its own failure domain.

**Goal-model interface (reuse, don't invent plumbing):**
- A training cycle = `Goal` (`objective: "cycle v<N> on dataset <manifest-id>"`, `max_steps` covering extract→scrub→train→merge→requant→eval→propose), claimed via `claim_next_goal` leases — the existing lease mechanism already prevents double-runs, which doubles as the guard against concurrent training jobs.
- Final step emits the promotion proposal through the normal verdict path; the HITL gate is *inherited*, not rebuilt.
- New config flag following the `NEXI_GOAL_DRIVER_ENABLED` precedent: `XTRAIN_AUTONOMOUS=false` default (manual trigger only).

**systemd / GPU exclusivity:**
- New `infra/no-k3s/node-b/systemd/xtrain-cycle.service` (`Type=oneshot`, `After=nvidia-ready.service`, `Restart=no`, `TimeoutStartSec=` hard wall-clock cap) declaring `Conflicts=vllm-ornith.service` plus the Vision Media Stack units, with the reciprocal lines added so the three-way group is fully pairwise-exclusive. Training is a **peer in the lock group, not a bypass**.
- Consequence embraced by design: starting a Train Window **stops production inference**. Therefore the start path is deliberately frictionful: approved Goal → explicit unit start → pre-flight asserts no other GPU unit transitioning → on exit (success *or* failure) the lock releases and `vllm-ornith.service` restarts via its existing `Restart=on-failure`/manual start. A crashed trainer must never wedge the GPU: `Restart=no` + timeout guarantee the lock frees.
- Vision stack interplay unchanged: whoever starts first owns the GPU; the other waits for a human-chosen moment.

### 5. Observability (Langfuse-first)

Added to the planned system-wide dashboards:
- **Job lifecycle:** one Langfuse trace per cycle — steps as spans (extract/scrub/train/merge/requant/eval), token/sample counts, scrub-manifest summary.
- **Eval series:** all five gate metrics per checkpoint ID over time, incumbent baseline line, eligibility verdict per candidate.
- **GPU contention timeline:** lightweight `nvidia-smi` poller on Node B emitting events (which unit holds the GPU, OOM events, vLLM restarts) — makes contention visible, not inferred.
- **Promotion/rollback events:** typed events with checkpoint IDs, approver, suite version; rollback rate is itself a dashboard metric.
- **Data health:** new-pair counts per source per week (early-warning that DPO is starving).

---

## Consequences

**Positive:** HITL signal finally compounds instead of evaporating; adaptation decisions become measurable (five numbers, versioned harness); the GPU stays governed by one exclusivity regime; promotion inherits a battle-tested security gate; solo-operable by construction (leases prevent double-runs, timeouts free the GPU, rollback is one command).

**Negative / accepted costs:** training windows are full inference outages (mitigated: evenings, optional audited Claude-route cover); ~82 h of phased build effort before any benefit; merge→requant discards hot-swap convenience; a second quantization pass introduces its own quality variance (caught by gate #5); two more moving services (xnch-train worker, poller).

### Risks (named, with mitigations)

| Risk | Reality | Mitigation |
|---|---|---|
| **Approver-pleasing overfitting** | DPO on approve/reject teaches "match this approver", not "be correct" — Goodhart's law on the nicest signal in the system | Mix SFT corpora (don't train preferences alone); stratified holdout by rejection reason; rank r≤32 and low LR as forgetting brakes; after any promotion, watch *live* HITL rejection rate as a canary with alert (auto-rollback deliberately deferred to Phase 3+) |
| **GPU contention degrading production** | Trainer OOM-crash loops colliding with vLLM's `RestartSec=15` restart cycle; wedged GPU | Peer `Conflicts=` membership; `Restart=no` + `TimeoutStartSec`; pre-flight transition check; lock-release verified post-run |
| **Sensitive context leaking into a shareable artifact** | LoRA/full checkpoints memorize; payment-adjacent data in a checkpoint that later gets exported | Scrub-before-dataset (with manifest); checkpoints classified as derived secrets; export/share requires HITL gate + audit; default posture: checkpoints never leave Node B |
| **Checkpoint sprawl** | Each release ≈ tens of GB on Node B NVMe; no policy = disk exhaustion mid-cycle | Immutable-ID registry from Phase 1; retention: incumbent + last 2 candidates + tagged releases; GC job in Phase 3; disk-quota alarm |

---

## Phased Plan (hour estimates, rough P0/P1 split)

House style per `docs/superpowers/plans/2026-08-17-goal-tracking-loop.md`: P0 = must-have to prove the phase; P1 = polish/robustness.

**Phase 0 — Data pipeline + eval harness only. No training. (~P0 14h / P1 6h)**
Extractors (Langfuse, verdicts, corrections, outcomes); scrubber + manifest + tests; canonical record format; eval harness v1 running *incumbent-only* to capture baselines for all five metrics; dry-run promotion-gate stub. Exit criteria: a valid, scrubbed, manifested dataset exists; baseline eval report exists.

**Phase 1 — Prove the loop on synthetic/held-out data, manual everything. (~P0 16h / P1 8h)**
Node B venv + pinned toolchain; QLoRA SFT on synthetic data; `xtrain-cycle.service` + three-way `Conflicts=` wiring; merge→requant path; full manual promotion drill *including a rollback drill*; first candidate-vs-incumbent eval report. Exit criteria: one complete Train→Promote→(revert) cycle executed end-to-end by hand. *(Empirically verify Q1 here.)*

**Phase 2 — Real production traces. (~P0 14h / P1 10h)**
Ship the three instrumentation fields; SFT on curated real successes; DPO stage activated once ≥ ~300 clean pairs (threshold confirmed in Phase 0 data audit); gate enforced as blocking; scrub-audit attached to every candidate. Exit criteria: first *real-data* candidate either promoted through the full HITL gate or rejected with a legible eval report — both are successes.

**Phase 3 — Trigger automation + hygiene. Still gated. (~P0 8h / P1 6h)**
Load/window-based scheduler that *proposes* training Goals (never auto-starts GPU takeover or promotion); checkpoint GC + retention policy; live canary alerting on post-promotion rejection rate; dashboard wiring completion.

**Total ≈ 82 h (P0 52 / P1 30).** Deliberately front-loaded: Phase 0 delivers standalone value (clean datasets + baselines) even if training is later abandoned in favor of the memory-first arm.

---

## Open Questions

1. **Q1 (resolve in Phase 1):** Does the deployed vLLM version support LoRA-over-`gptq_marlin` adequately? If yes, hot-served adapters become a cheaper promotion path than merge→requant — re-evaluate Decision §2 then.
2. What does the episodic store expose *today* for correction linkage — does `corrects_decision_id` exist in any form, or is the Phase-2 instrumentation the true minimum?
3. What is the real accumulation rate of usable HITL pairs? (Phase 0 data audit answers this and validates/adjusts the 300-pair DPO threshold.)
4. Should the Claude-API opt-in route auto-arm during *approved* training windows, or stay manually engaged per window?
5. Can the original Ornith GPTQ-Pro quantization recipe (toolchain + calibration set) be recovered, so merged-checkpoint requants match incumbent quant quality? If not, accept the gate-#5 tolerance as the contract.
6. Long-term dataset home: Node A filesystem with backups, or Postgres-backed? (Decide by end of Phase 0.)
