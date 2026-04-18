# Decision Model

---
tags:
  - #architecture
  - #decision
  - #nexi
---

How Nexi makes decisions. The logic, not the implementation.

For module-level architecture (what each sub-component does), see [[nexi.md]]. For the runtime flow mapped to process steps, see [[execution-flow.md]].

---

## Decision Pipeline

A decision in Nexi is not a single inference. It is a multi-stage pipeline that transforms ambiguous input into a structured, policy-verified, scored selection — with a full audit record of the reasoning.

```
Raw Input
    │
    ▼
[1] Intent Normalization
    Ambiguous? ──▶ CLARIFICATION_REQUIRED (session paused)
    │
    ▼
[2] Context Loading
    Pull: episodes, patterns, active policies for this (intent_class, entity_class, actor_role)
    Pin: system_state_version — immutable for session lifetime
    │
    ▼
[3] Option Generation
    Model produces N structured candidates (default N=5)
    Output schema enforced — model generates only, does not evaluate or rank
    │
    ▼
[4] Policy Alignment Filter
    Parallel dry-run against xnch for each option
    BLOCK → dropped immediately
    MODIFY → action spec rewritten by xnch, flagged in record
    DEFER → retained, marked as requiring secondary auth
    All BLOCK? → ESCALATE (no selection forced)
    │
    ▼
[5] Scoring
    Four dimensions scored independently per surviving option
    Weighted composite computed per intent_class weight profile
    │
    ▼
[6] Outcome Simulation (conditional)
    Forward-project top 2 options against current system state
    Constraint violation → re-score with risk penalty
    All options violate → ESCALATE
    │
    ▼
[7] Selection
    Highest composite score, non-blocked, non-escalated option selected
    Decision record assembled with full scoring artifact
    │
    ▼
[8] Verdict Submission
    Full decision record submitted to xnch /verdict (not just the action leaf)
    xnch re-evaluates — this is the authoritative check, not the dry-run
```

---

## Option Generation Strategy

### Model as Constrained Generator

The model is called exactly once per session, in the Option Generator module. It is not asked to evaluate, rank, or select. It is asked to generate a structured set of distinct candidate approaches.

The generation request contains:
- Normalized intent (not raw text)
- A summary of relevant context (entity history, dominant patterns) — not raw episodes
- An output schema the model must conform to
- Explicit instruction: "Generate only. Do not evaluate. Do not select."

The model is not told which option will be selected. Anchoring bias in option generation (generating options that cluster around a single approach because the model "thinks" one is right) is avoided by withholding evaluative framing from the prompt.

### Option Set Bounds

| Bound | Value | Reason |
|-------|-------|--------|
| Minimum | 3 | Below 3, ranking is meaningless |
| Default | 5 | Sufficient diversity, manageable evaluation cost |
| Maximum | 7 | Above 7, marginal option quality gain does not justify evaluation cost |

On CPU fallback (llama-cpp-python active), the cap is reduced to 3 to limit generation latency.

### Model Output is Untrusted

Model output is treated as raw candidate material. It undergoes schema validation before any further processing. If the model returns malformed output, Nexi retries once with a stricter prompt. On second failure, a rule-based fallback generator produces 3 conservative options directly from policy memory. The fallback path is recorded in the decision record as `generation_path: RULE_BASED`.

---

## Evaluation Criteria

Four dimensions. Each is scored independently on [0, 1]. They are not correlated with each other by design — a high-compliance option can have low efficiency, and that is a valid trade-off that the weight profile resolves.

### Policy Score

Derived directly from the xnch dry-run verdict. Not computed by Nexi independently.

| Verdict | Score |
|---------|-------|
| `ALLOW` | 1.0 |
| `ALLOW_WITH_WARNINGS` | 0.7 |
| `MODIFY` | 0.5 |
| `DEFER` | 0.3 |
| `BLOCK` | Option dropped — not scored |

The policy score is anchored to xnch's authoritative policy evaluation, not to Nexi's own assessment of compliance. Nexi does not maintain a local policy evaluator.

### Outcome Score

Pattern lookup against episodic history loaded in the context manifest.

```
outcome_score = pattern.success_rate × pattern.confidence
```

If no pattern exists for the `(action_type, entity_class)` tuple (first-time action or insufficient episodes), `outcome_score` defaults to 0.5 — neither optimistic nor pessimistic. A recency adjustment is applied: episodes in the most recent 7 days are weighted 1.5× relative to older episodes when computing `success_rate`.

If the most recent 3 episodes for a tuple are all failures, a recency penalty of −0.2 is applied to `outcome_score` regardless of the aggregate pattern.

### Risk Score

Composite of four sub-signals, each binary or normalized:

| Sub-signal | High-risk condition | Contribution |
|------------|--------------------|----|
| Reversibility | `option.reversible = false` | +0.3 |
| Entity sensitivity | `entity_class` in high-sensitivity set (e.g., `PRODUCTION_DB`, `AUTH_SERVICE`) | +0.2 |
| Side effect count | `len(estimated_side_effects) > 2` | +0.1 per additional effect above 2, capped at +0.3 |
| Actor type | `actor.type = AGENT` | +0.2 |

The score is clamped to [0, 1]. Risk score is the dimension most likely to trigger Outcome Simulation and most heavily weighted for `CRITICAL` and `EXECUTION` intent classes.

Risk score is directional: higher = more risky. In the composite formula, risk is weighted as a cost, not a benefit.

### Context Fit Score

Structural coverage ratio between the option's `action_spec` and the intent's declared constraints.

```
context_fit = matched_constraint_fields / total_constraint_fields
```

If the intent declares no explicit constraints, `context_fit` defaults to 0.6 — partial credit for being any valid approach. This dimension is the lightest-weighted by default because it is the least predictive of actual outcome quality — it measures how well the option addresses what was asked, not whether addressing it will succeed.

---

## Scoring Mechanism

Each intent class has a weight profile. Weight profiles are versioned and stored in xnch — they are not hardcoded. The active version is pinned from the context manifest at session start.

**Default weight profiles:**

| Intent Class | Policy | Outcome | Risk | Context Fit |
|-------------|--------|---------|------|-------------|
| `QUERY` | 0.20 | 0.25 | 0.15 | 0.40 |
| `EXECUTION` | 0.25 | 0.30 | 0.35 | 0.10 |
| `DECISION` | 0.30 | 0.30 | 0.25 | 0.15 |
| `ESCALATION` | 0.40 | 0.20 | 0.30 | 0.10 |
| `CRITICAL` urgency override | +0.10 to risk | −0.10 from context_fit | — | — |

`QUERY` weights context fit heavily because the primary risk is returning irrelevant information, not causing side effects. `EXECUTION` weights risk most heavily because the primary risk is irreversible real-world effects.

**Composite formula:**
```
composite = (policy × w_policy) + (outcome × w_outcome) + (risk × w_risk) + (context_fit × w_context_fit)
```

Where `w_risk` is applied inversely — risk_score of 1.0 contributes 0.0 to composite for that dimension:
```
risk_contribution = (1.0 - risk_score) × w_risk
```

**Confidence:** The margin between the selected option's composite and the second-best option's composite. Low margin (< 0.10) is recorded in the decision record. It does not block selection but is surfaced in the audit trail.

---

## How Feedback Updates Future Decisions

The feedback loop is outcome-grounded — it updates based on what happened in the world, not on what the model predicted.

### Feedback Signal

After execution completes, the Execution Outcome record is written to the Episodic Store. Each episode records:
- The actual outcome (`SUCCESS | PARTIAL | FAILURE`)
- `prediction_delta`: how wrong the `outcome_score` was (`abs(predicted - actual)`)

### Pattern Update

Every 6 hours, the Pattern Extractor recomputes `success_rate` and `confidence` for each `(action_type, entity_class)` tuple from accumulated episodes. Updated patterns are what future sessions read as `outcome_score`.

**Early extraction:** When `prediction_delta > 0.3` for any single episode, the Pattern Extractor is triggered immediately rather than waiting for the scheduled run. Large prediction errors carry more signal about miscalibration than gradual drift.

### Weight Update

The Score Adapter monitors per-dimension prediction accuracy (correlation between the dimension's score prediction and the actual binary outcome). When accuracy drops below 0.6 for any dimension:

1. A weight adjustment is proposed
2. Submitted to xnch as a `POLICY_CHECK`
3. Applied only after xnch approval
4. Versioned — every weight change has a causative episode batch reference and an audit trail

This mechanism prevents a single bad episode batch from corrupting the weight configuration. Weight updates are governed, not automatic.

### What Improves

The model does not change. The weight configurations converge toward profiles that have historically produced better outcomes. The pattern store accumulates signal, making `outcome_score` increasingly predictive. Option prompts (template versions) are revised when patterns show that options of a given type consistently score well in generation but poorly in outcomes — indicating the prompt is generating plausible-sounding but poorly-calibrated options.

---

## Exploration vs Exploitation

Nexi is an exploitation system by default. It selects the highest-scoring option from the current evaluation — it does not explore deliberately.

Exploration emerges from two sources:

1. **Model diversity in generation.** The model is prompted for distinct options, not variations on one theme. Temperature is set above 0 (default: 0.7). Different generation calls for the same intent will produce different option sets. There is no ranking injected into the prompt that would cause the model to cluster around one approach.

2. **Low-confidence handling.** When `confidence` (margin between first and second option) is below 0.10, the decision record flags it. An operator review can request a new session with a different random seed, effectively forcing a new exploration of the option space.

There is no epsilon-greedy or UCB mechanism. The system is not a bandit. Deliberate exploration in a governed system that executes real-world actions (deploys, mutations, API calls) is architecturally inappropriate — the cost of exploring a bad action is not bounded the way it is in a simulation or recommendation context.

---

## When Simulation is Triggered

The Outcome Simulator runs forward-projection for the top 2 options (by composite score before simulation) when any of the following is true:

| Condition | Reason |
|-----------|--------|
| `risk_score > 0.6` for any surviving option | High-risk options may produce constraint-violating states not captured by static scoring |
| `option.reversible = false` | Irreversible actions cannot be corrected post-execution |
| `actor.type = AGENT` | Agents have no human judgment as a backstop |
| `intent_class = EXECUTION` + `urgency = CRITICAL` | Combined urgency and real-world effect |

Simulation is not run for all options — only the top 2 by pre-simulation composite. Running simulation on all options would add latency proportional to the option set size; the low-scoring options are unlikely to be selected regardless.

**Simulation result:**
- Projected state does not violate constraints → no change to scores
- Projected state violates a loaded constraint → `risk_score += 0.3` (capped at 1.0), composite recalculated
- All projected states violate constraints → ESCALATE; no option selected

---

## Failure and Uncertainty Handling

| Condition | Handling |
|-----------|----------|
| `ambiguity_score > 0.7` | Session paused; `CLARIFICATION_REQUIRED` returned; reasoning does not proceed on ambiguous intent |
| All options blocked by policy filter | `ESCALATED`; hold record written to xnch with `required_actor`; no selection forced |
| All options project to constraint-violating states | `ESCALATED`; same path as above |
| Model generation fails (2 attempts) | Rule-based fallback activated; 3 conservative options from policy memory; `generation_path = RULE_BASED` in decision record |
| xnch final verdict = `BLOCK` (after dry-run passed) | `ESCALATED`; Nexi does not retry with next-best option; a state change occurred between dry-run and final verdict, requiring human review |
| Context manifest unavailable | Hard stop; `DEGRADED` status returned; Nexi does not reason without context |
| Low confidence (margin < 0.10) | Selection proceeds; margin recorded in decision record; no automatic escalation |

Nexi does not force a selection under uncertainty. Every escalation path is preferable to selecting an option when the system cannot reason about it reliably. The decision record always contains the full trace of why a session escalated or degraded, making the escalation itself auditable.

---

## Confidence Calibration

### Initial Confidence Computation

Confidence in the Decision Record is the **margin** between the selected option's composite score and the second-best option's composite score:

```
confidence = selected.composite - second_best.composite
```

This is not a probability. It is a relative measure of how clearly one option dominates. A confidence of 0.30 means the selected option outscored the next-best by 0.30 on a [0,1] scale. A confidence of 0.02 means the scores are nearly identical and the selection is effectively a tie.

Confidence is computed after all scoring is complete — including any simulation re-scoring. It reflects the final ranked state of evaluated options.

### Confidence Thresholds

| Level | Margin | System Behavior |
|-------|--------|----------------|
| High | ≥ 0.20 | Selection proceeds; no additional flags |
| Medium | 0.10 – 0.19 | Selection proceeds; margin noted in Decision Record |
| Low | < 0.10 | Selection proceeds; `low_confidence` flag set in Decision Record; surfaced in audit trail; operator may request re-session with different seed |

There is no threshold below which Nexi refuses to select. Confidence is an observational signal, not a gate. Escalation is triggered by structural failures (all options blocked, all simulate to violations), not by low margin. A system that escalates on low confidence would escalate on genuinely difficult decisions — exactly the cases where the system should still produce a governed output.

### Adjustment Using Outcomes

Confidence as computed at decision time is a forward-looking score margin. It is calibrated over time by comparing it against actual outcomes.

**Mechanism:**

After a session completes, the episode records `prediction_delta = abs(outcome_score_predicted - actual_success_rate)`. For sessions where `confidence` was high (≥ 0.20) but `prediction_delta` was also high (> 0.3), the Score Adapter accumulates a signal that the evaluation weights are producing overconfident selections in this context signature.

This feeds into weight adjustment (see `How Feedback Updates Future Decisions`) — reducing the effective weight of the dimension most predictive of that overconfidence, which in turn narrows future composite margins for similar intents and produces more conservative (lower, but better-calibrated) confidence values.

**Calibration does not modify the confidence formula.** It modifies the weights that produce the scores the formula operates on. Confidence remains a margin — it is the scores that become better-calibrated.

### Unreliability Conditions

Confidence values are unreliable (and should be treated as informational only) under the following conditions:

| Condition | Indicator | Effect on Confidence |
|-----------|-----------|---------------------|
| Low sample size | `pattern.observation_count < 10` for all matched patterns | `outcome_score` defaults to 0.5 (uninformed prior); composite scores cluster near the prior; margin is artifactually small |
| Conflicting outcomes | `pattern.avg_prediction_delta > 0.4` | Pattern is poorly calibrated; `outcome_score` contribution is noisy; margin does not reflect genuine option quality difference |
| High variance context | Episodes for this context signature show `SUCCESS` and `FAILURE` alternating without clear trend | `success_rate` is near 0.5 regardless of sample size; `outcome_score` contributes near-zero differentiation; confidence margin reflects only `policy_score`, `risk_score`, and `context_fit_score` differentiation |
| `generation_path = RULE_BASED` | Model unavailable; options generated from policy memory | Options are deliberately conservative and similar by design; margins will be artificially small |

When any unreliability condition is detected, it is recorded in the Decision Record alongside `confidence`. Operators querying audit history can filter by these flags.

### Escalation Rules Triggered by Confidence

Confidence alone does not escalate. The following escalation rules involve confidence as a contributing signal in combination with other conditions:

| Rule | Condition | Trigger |
|------|-----------|---------|
| Human gate | `confidence < 0.10` AND `intent_class = EXECUTION` AND `option.reversible = false` | Simulation is forced (if not already running); result reviewed before token issuance |
| Simulation trigger | `confidence < 0.15` AND `risk_score > 0.5` for top option | Outcome Simulator activated even if risk threshold (0.6) is not independently met |
| Operator flag | `confidence < 0.10` in Decision Record | `low_confidence` flag surfaced in audit query results; operator may request re-session |
| No escalation | `confidence < 0.10` alone | Selection proceeds normally; low confidence without structural failure is not an escalation condition |

---

## Decision Traceability

### Scoring Contributions

Every Decision Record contains the full scoring artifact — not just the selected option, but the complete evaluation of all surviving options. Each dimension's contribution to the composite score is independently recorded and reconstructible.

**Per-option scoring breakdown stored in Decision Record:**

```json
{
  "option_id": "uuid",
  "scores": {
    "policy_score": 1.0,
    "outcome_score": 0.46,
    "risk_score": 0.55,
    "context_fit_score": 0.90
  },
  "risk_contribution": 0.45,
  "composite_score": 0.68,
  "policy_verdict": "ALLOW",
  "simulation_ran": true,
  "simulation_adjusted_risk": false
}
```

`risk_contribution = (1.0 - risk_score) × w_risk` — stored separately to make the inversion explicit in the audit record, so a reviewer does not have to reconstruct the formula.

### Final Weighted Score Formula (Reconstructible)

```
composite = (policy_score    × w_policy)
          + (outcome_score   × w_outcome)
          + ((1.0 - risk_score) × w_risk)
          + (context_fit_score  × w_context_fit)
```

Weight values are not stored in the Decision Record inline — they are referenced by `weight_config_version`. The weight config is versioned and immutable once deployed. Given `weight_config_version`, the exact weights used at decision time can be retrieved from xnch's governance store, and the composite score can be recomputed from the stored dimension scores and verified to match.

### Decision Reconstruction

A decision made at time T can be fully reconstructed from stored artifacts:

| Artifact | Contains | Source |
|----------|----------|--------|
| Decision Record | All options, all scores, selected option, `weight_config_version`, `context_manifest_ref`, `confidence` | xnch audit store |
| Context Manifest | Episodes, patterns, policies active at session time | xnch memory (pinned version) |
| Weight Config | Dimension weights for `weight_config_version` | xnch governance store |
| Audit Ledger Entry | Verdict, policy refs evaluated, actor, timestamp, action payload hash | Audit logger (append-only JSONL) |
| Episode | Actual outcome of the decision | Episodic Store |

**Reconstruction steps:**

1. Retrieve Decision Record by `decision_id`
2. Retrieve Weight Config by `weight_config_version` from governance store
3. Recompute composite for each option: verify stored composites match formula output
4. Retrieve Context Manifest by `context_manifest_ref`: verify patterns and policies were as recorded
5. Retrieve Audit Ledger Entry by `audit_ref`: verify verdict and policy refs
6. Retrieve Episode by `decision_id`: verify actual outcome vs predicted `outcome_score`

Any divergence between stored scores and recomputed scores indicates either a bug in the scoring logic at decision time or a tampered record. The SHA-256 chain in the Decision Ledger detects the latter.

### Audit Linkage

The following identifiers thread through the complete audit chain for a single loop iteration:

```
trace_id          — threads through all log events (Event Log)
  └── session_id      — session scope
        └── decision_id   — decision scope
              ├── audit_ref     — Audit Ledger entry reference (returned to actor)
              ├── execution_ref — execution scope
              │     └── execution_token_ref — token used at dispatch
              └── episode_id    — learning record (written after execution)
```

**Replay capability:**

The Replay Engine (see [`components/audit.md`](../components/audit.md)) can re-run the decision logic for any `decision_id` using the stored Context Manifest and Weight Config from that session. It re-scores all options against the stored context and produces a `ReplayResult` showing whether the same option would be selected under:

- The original weights (`weight_config_version` at decision time)
- The current weights (current weight config version)
- A supplied alternate weight config (what-if analysis)

This allows operators to verify that a historical decision was correct under the policies and weights in effect at the time, and to evaluate how the system's judgment has evolved since then.

---

## Related

- [[_decision-map.md]]
- [[nexi.md]]
