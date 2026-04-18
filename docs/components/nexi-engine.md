# Nexi Engine

---
tags:
  - #component
  - #nexi
  - #decision
---

The decision engine. Receives a session context from xnch, generates candidate plans, filters and scores them, and submits a decision record back to xnch. Does not execute. Does not write memory directly.

For internal architecture, module definitions, and design rationale, see [[nexi.md]].

---

## Related

- [[nexi.md]]
- [[decision-model.md]]

---

## Instantiation

```python
from xnch.nexi import NexiEngine, NexiConfig

config = NexiConfig.from_file("~/.xnch/config.yaml")
engine = NexiEngine(config)
```

---

## Primary API

```python
class NexiEngine:
    def execute(self, intent: Intent) -> NexiResult:
        """Run full decision pipeline. Returns decision package."""

    def generate_options(self, intent: Intent) -> list[Plan]:
        """Generate candidate plans only — no filtering or selection."""

    def evaluate(self, plans: list[Plan]) -> list[EvaluatedPlan]:
        """Score plans without generating new options."""

    def select(self, evaluated: list[EvaluatedPlan]) -> tuple[Plan, str]:
        """Select final plan. Returns (plan, decision_token)."""
```

### NexiResult

```python
class NexiResult:
    session_id: str
    decision_id: str
    trace_id: str
    status: str              # DECIDED | ESCALATED | CLARIFICATION_REQUIRED | DEGRADED
    verdict_ref: str
    selected_action: dict    # action_type, action_spec, execution_token, token_ttl_ms
    decision_record_ref: str
    escalation: dict | None  # reason, required_actor, hold_id
    clarification: dict | None
```

---

## Configuration

```yaml
nexi:
  host: localhost
  port: 8200

  max_candidates: 5          # number of options generated per session (3–7)

  option_generator:
    temperature: 0.7
    max_tokens: 2048
    top_p: 0.9

  evaluation:
    weights:                 # per intent_class; these are defaults
      safety: 0.30
      efficiency: 0.25
      compliance: 0.25
      context_fit: 0.20

  policy_paths:
    - ~/.xnch/policies/default.yaml
    - ~/.xnch/policies/custom.yaml

  outcome_simulator:
    enabled: true
    risk_threshold: 0.6      # simulate when risk_score exceeds this
```

---

## Session Flow

Each call to `execute()` opens a session with xnch and runs the full pipeline:

```
session init → intent interpretation → context manifest load
  → option generation → parallel policy dry-run
  → scoring → outcome simulation (conditional)
  → decision selection → POST /verdict to xnch
  → return NexiResult
```

A session is stateless on Nexi's side. All persistent state lives in xnch.

---

## Degraded Mode

If the model layer fails (timeout or schema validation failure on retry), Nexi activates a rule-based option generator that produces 3 conservative options from policy memory. The `NexiResult.status` is set to `DEGRADED` and the decision record notes the degraded generation path.

Nexi does not fail closed on model unavailability. It fails to a deterministic fallback.

---

## Escalation

Nexi escalates (rather than selecting) in three cases:

1. All generated options are blocked by xnch policy dry-run
2. All options simulate to constraint-violating projected states
3. xnch returns `BLOCK` on the final `/verdict` call

Escalation writes a hold record to xnch and returns `status: ESCALATED` with `hold_id` and `required_actor`. No execution token is issued. The session is preserved pending admin resolution.

---

## Monitoring

```yaml
metrics:
  nexi:
    sessions_total: true
    options_generated: true
    options_blocked: true
    decisions_escalated: true
    model_fallback_total: true
    latency_ms:
      intent_interpretation: true
      context_load: true
      option_generation: true
      policy_filter: true
      scoring: true
      simulation: true
      verdict_submission: true
```
