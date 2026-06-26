# Implementation Contracts

---
tags:
  - #reference
  - #contracts
  - #policy
---

Boundary-level specifications for components that must interoperate. Each contract defines the exact format, algorithm, or protocol a component must implement. These are not architecture descriptions — they are build targets.

For data structure schemas, see [[data-contracts.md]]. For system-wide behavior, see [[../architecture/system-loop.md]].

---

## Contract 1: Policy DSL

**Owner:** xnch-server  
**Storage:** `~/.xnch/policies/` (default.yaml + custom.yaml)  
**Format:** YAML  
**Immutability:** A deployed policy version is never modified in place. Updates produce a new version file. The active version pointer is updated atomically.

### Rule Structure

```yaml
version: "1.0"          # semver, required
policy_id: "string"     # unique identifier, required
description: "string"   # human-readable, required
rules:
  - rule_id: "string"           # unique within policy, required
    priority: integer           # lower = evaluated first; range [1, 999]
    conditions:
      intent_class: "QUERY | DECISION | EXECUTION | ESCALATION"   # optional
      action_type: "string"                                        # optional; exact match
      entity_class: "string"                                       # optional; exact match
      actor_role: "string"                                         # optional; exact match
      actor_capabilities: ["string"]                               # optional; all must be present
      urgency: "LOW | NORMAL | HIGH | CRITICAL"                    # optional
      reversible: true | false                                     # optional
      time_window:
        days: ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]  # optional
        hours_utc: "HH:MM-HH:MM"                                  # optional; 24h format
    action:
      verdict: "ALLOW | ALLOW_WITH_WARNINGS | BLOCK | MODIFY | DEFER"
      reason: "string"          # required; included in policy_refs on policy dry-run response
      warnings: ["string"]      # required only when verdict = ALLOW_WITH_WARNINGS
      modify_spec:              # required only when verdict = MODIFY
        field: "string"         # dot-path into action_spec
        value: "any"
      requires_actor: "string"  # required only when verdict = DEFER; actor_role target
```

### Condition Evaluation

- All declared condition fields are ANDed. An omitted field matches any value.
- `actor_capabilities` is satisfied when the actor's `capability_set` contains **all** listed strings.
- `time_window.days` and `time_window.hours_utc` are ANDed when both are present.
- Conditions are evaluated against the session's pinned `system_state_version` snapshot — never live state.

### Evaluation Model

Rules are evaluated in ascending `priority` order. First matching rule determines the verdict.

```
for each rule in ascending priority:
    if all conditions match:
        return rule.action.verdict
return ALLOW   # default when no rule matches
```

**No implicit BLOCK.** A policy that defines no matching rule returns `ALLOW`. To deny by default, add a catch-all rule at priority 999 with no conditions and `verdict: BLOCK`.

### Conflict Resolution

When two rules match the same input (duplicate priority is a configuration error):

1. Lower `priority` value wins unconditionally.
2. If priorities are equal: `BLOCK` takes precedence over `ALLOW`.
3. `MODIFY` and `DEFER` do not supersede `BLOCK`.

Duplicate priorities are logged as a warning at policy load time. The policy is not rejected.

Priority uniqueness is enforced across the merged ruleset (default + custom combined), not within each file individually. A rule with priority N in `default.yaml` and a rule with priority N in `custom.yaml` constitute a duplicate priority collision.

### Examples

**Deployment restriction by time window:**
```yaml
- rule_id: "no-weekend-deploys"
  priority: 10
  conditions:
    action_type: "deploy"
    time_window:
      days: ["SAT", "SUN"]
  action:
    verdict: BLOCK
    reason: "Deployments are restricted on weekends (policy: ops-safety)"
```

**Rate limiting by actor role:**
```yaml
- rule_id: "agent-execution-rate"
  priority: 20
  conditions:
    actor_role: "AGENT"
    intent_class: "EXECUTION"
  action:
    verdict: ALLOW
    reason: "Agent execution allowed; rate enforcement at KV Cache layer"
```

**Role-based capability control:**
```yaml
- rule_id: "require-admin-for-schema-change"
  priority: 5
  conditions:
    action_type: "alter_schema"
    actor_capabilities: []
  action:
    verdict: BLOCK
    reason: "Schema changes require admin capability"

- rule_id: "allow-admin-schema-change"
  priority: 4
  conditions:
    action_type: "alter_schema"
    actor_capabilities: ["admin", "schema_write"]
  action:
    verdict: ALLOW
    reason: "Actor has required capabilities"
```

### Version File Layout

```
~/.xnch/policies/
  default.yaml          # base policy, always loaded
  custom.yaml           # operator overrides, loaded after default
  archive/
    default-v1.0.yaml   # previous versions, never deleted
    custom-v1.2.yaml
```

Policy load order: `default.yaml` rules first, then `custom.yaml` rules appended. `custom.yaml` rules at the same priority as `default.yaml` rules are evaluated after default rules (implicit priority advantage to default).

---

## Contract 2: Execution Token JWT

**Issuer:** xnch-server  
**Validator:** execution-runner (independently, without calling xnch)  
**Algorithm:** RS256 (RSASSA-PKCS1-v1_5 with SHA-256)  
**Key storage:** xnch holds private key; public key published at `GET /auth/public-key`

### Payload Schema

```json
{
  "iss": "xnch",
  "sub": "execution_token",
  "jti": "<uuid-v4>",
  "iat": "<unix-seconds>",
  "exp": "<unix-seconds>",
  "session_id": "<uuid-v4>",
  "decision_id": "<uuid-v4>",
  "trace_id": "<uuid-v4>",
  "actor_id": "<string>",
  "actor_role": "<string>",
  "action_type": "<string>",
  "entity_class": "<string>",
  "policy_version": "<string>",
  "system_state_version": "<integer>",
  "token_ttl_ms": 30000
}
```

All fields are required. No optional fields. No additional fields are written into the token.

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `iss` | string | Always the literal string `"xnch"` |
| `sub` | string | Always the literal string `"execution_token"` |
| `jti` | uuid-v4 | Unique token ID; used for replay protection |
| `iat` | unix-seconds | Issuance time (UTC) |
| `exp` | unix-seconds | `iat + 30`; execution-runner rejects tokens past this time |
| `session_id` | uuid-v4 | Session that produced this verdict |
| `decision_id` | uuid-v4 | Decision Record this token authorizes |
| `trace_id` | uuid-v4 | Trace propagated through the full session |
| `actor_id` | string | Actor identity from session context |
| `actor_role` | string | Actor role at time of verdict |
| `action_type` | string | Authorized action type; runner must confirm dispatch matches |
| `entity_class` | string | Entity class the action targets |
| `policy_version` | string | Policy version active at verdict time |
| `system_state_version` | integer | State version pinned at session init |
| `token_ttl_ms` | integer | Always 30000; informational only — `exp` is authoritative |

### Validation Rules (execution-runner)

The execution-runner performs these checks in order before accepting a dispatch:

1. Verify RS256 signature against xnch public key (fetched at startup, cached; refresh on 401 from xnch).
2. Confirm `iss == "xnch"`.
3. Confirm `sub == "execution_token"`.
4. Confirm current time < `exp` (token not expired).
5. Confirm `jti` has not been seen before (replay protection — runner maintains an in-memory `jti` set per process lifetime; TTL-evict entries after `exp` passes).
6. Confirm `action_type` in dispatch payload matches `action_type` in token.
7. Confirm `entity_class` in dispatch payload matches `entity_class` in token.

Token consumption rule: the `jti` is added to the seen-set on the **first presentation** of the token, regardless of whether subsequent checks pass. Once consumed, re-presentation of the same `jti` fails check 5. Do not execute if any check fails.

### Replay Protection

- The `jti` is consumed (added to the seen-set) on first presentation, before execution. A token that fails checks 2–7 is still consumed — it cannot be re-presented.
- The `jti` set is in-process memory only. On runner restart, the set is empty.
- Tokens expire in 30s. If the runner restarts within a token's validity window, a replayed `jti` could pass. Acceptable — token window is 30s and replays require a valid RS256 signature.
- xnch does not maintain a `jti` blocklist. Replay protection responsibility is entirely on the runner.

---

## Contract 3: Context Signature

**Producer:** memory-store (Pattern Store lookup key)  
**Consumer:** nexi-engine (pattern retrieval and episode storage)  
**Purpose:** Deterministic identifier for the context tuple that a Pattern record represents.

### Input Fields

```
intent_class    string   one of: QUERY, DECISION, EXECUTION, ESCALATION
action_type     string   exact action_type from Plan Option
entity_class    string   exact entity_class from session context
actor_role      string   exact actor_role from session context
```

### Canonical Serialization

Fields are concatenated in fixed order with `|` as delimiter. No whitespace. All values are lowercased before concatenation.

```
<intent_class_lower>|<action_type_lower>|<entity_class_lower>|<actor_role_lower>
```

### Algorithm

```python
import hashlib

def compute_context_signature(
    intent_class: str,
    action_type: str,
    entity_class: str,
    actor_role: str,
) -> str:
    canonical = "|".join([
        intent_class.lower(),
        action_type.lower(),
        entity_class.lower(),
        actor_role.lower(),
    ])
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
```

### Example

Input:
```
intent_class = "EXECUTION"
action_type  = "deploy"
entity_class = "service"
actor_role   = "OPERATOR"
```

Canonical string: `execution|deploy|service|operator`

Output: `sha256:` + SHA-256 hex digest of UTF-8 encoding of `execution|deploy|service|operator`

### Determinism Requirements

- All implementations (Python, any future language) must produce identical output for identical inputs.
- Field order is fixed. Deviation produces a different signature and breaks pattern lookup.
- Lowercasing is applied before concatenation, not after. `"DEPLOY"` and `"deploy"` must produce the same signature.
- The `sha256:` prefix is part of the stored value. It is not stripped before comparison.

### Null / Missing Fields

If any input field is absent or null, the signature computation must not proceed. Return an error. A partial signature is not defined and must never be stored.

---

## Contract 4: Intent Classification Contract

**Producer:** intent-parser (inside nexi-engine)  
**Consumer:** nexi-engine pipeline, xnch session context  
**Input:** raw natural language string from actor  
**Output:** normalized Intent object (see `data-contracts.md — Intent`)

### Classification Strategy

Two-stage classification:

**Stage 1 — Rule-based pre-filter:**  
Match `raw_input` against keyword and pattern rules before calling the model. If a rule matches with confidence ≥ 0.95, skip model call and emit rule-matched result.

Rule examples (not exhaustive):
```
"list *"          → intent_class = QUERY,     action_type = list
"show *"          → intent_class = QUERY,     action_type = read_file
"deploy *"        → intent_class = EXECUTION, action_type = deploy
"back(up|fill) *" → intent_class = EXECUTION, action_type = backup
"plan *"          → intent_class = DECISION,  action_type = plan
"escalate *"      → intent_class = ESCALATION, action_type = escalate
```

**Stage 2 — Model-based classification:**  
Submit `raw_input` to vllm-primary (or fallback path) with a constrained classification prompt. The prompt must request structured JSON output with the following fields:

```json
{
  "intent_class": "QUERY | DECISION | EXECUTION | ESCALATION",
  "action_type": "string",
  "target_entity": "string",
  "target_entity_class": "string",
  "constraints_declared": ["string"],
  "urgency": "LOW | NORMAL | HIGH | CRITICAL",
  "ambiguity_score": float,
  "confidence": float
}
```

### Output Schema

The classified Intent must conform to the Intent structure in `data-contracts.md`. Additional fields for internal use:

| Field | Type | Constraint |
|-------|------|------------|
| `intent_class` | string | Must be one of: `QUERY`, `DECISION`, `EXECUTION`, `ESCALATION` (uppercase) |
| `action_type` | string | Uppercase canonical form; from the defined vocabulary below |
| `confidence` | float | [0.0, 1.0] |
| `ambiguity_score` | float | [0.0, 1.0]; >0.7 triggers CLARIFICATION_REQUIRED |
| `classification_method` | string | `"rule"` or `"model"` |

`confidence` and `classification_method` are internal to the intent-parser. They are not included in the Intent object emitted to downstream components and are not persisted.

### Intent Class Definitions

| Canonical Class | Description |
|-----------------|-------------|
| `QUERY` | Read-only information retrieval; no state change |
| `DECISION` | Request for a recommended course of action; no immediate execution |
| `EXECUTION` | Request to perform a state-changing operation |
| `ESCALATION` | Request that requires actor elevation or human-in-the-loop review |

### Action Type Vocabulary

The canonical action type vocabulary uses uppercase values, consistent with `data-contracts.md — Plan Option`. The intent-parser classifies using lowercase internal forms; the normalization step (see Normalization Contract) converts to the canonical uppercase form before the Intent object is emitted.

| Canonical (uppercase) | Lowercase internal | Description |
|----------------------|-------------------|-------------|
| `READ_FILE` | `read_file` | Read file or resource content |
| `WRITE_FILE` | `write_file` | Write to file or resource |
| `DELETE_FILE` | `delete_file` | Delete file or resource |
| `LIST` | `list` | List resources |
| `RUN_COMMAND` | `run_command` | Execute a shell command |
| `RUN_SCRIPT` | `run_script` | Execute a script |
| `DEPLOY` | `deploy` | Deploy a service or artifact |
| `ROLLBACK` | `rollback` | Roll back a deployment |
| `STAGE` | `stage` | Stage a deployment step without finalizing |
| `MUTATE` | `mutate` | Mutate structured data (subsumes `alter_schema`, `migrate`) |
| `BACKUP` | `backup` | Create a backup |
| `RESTORE` | `restore` | Restore from backup |
| `PLAN` | `plan` | Produce a plan without executing |
| `ANALYZE` | `analyze` | Analyze without state change |
| `ESCALATE` | `escalate` | Escalate to operator or higher-authority actor |
| `QUERY` | `query` | Query structured data (distinct from QUERY intent class — see note below) |

**Note:** `QUERY` as an action type is a structured data query (e.g., read or filter). It is distinct from the `QUERY` intent class, which describes read-only information retrieval at the intent level. An intent classified as `QUERY` may use any action type that produces no state change.

Unknown action types are preserved verbatim in uppercase. They are not rejected at classification. Policy evaluation handles unknown types via the default `ALLOW` (no matching rule = ALLOW; see Contract 1 Evaluation Model).

### Fallback on Uncertainty

When `confidence < 0.7` or `ambiguity_score > 0.7`:

1. If `ambiguity_score > 0.7`: set session status to `CLARIFICATION_REQUIRED`; do not proceed to context loading.
2. If `confidence < 0.7` and `ambiguity_score ≤ 0.7`: proceed with classified intent; set `ambiguity_score` to `1.0 - confidence`; flag in Intent as ambiguous.
3. Rule-based pre-filter results are always passed with `confidence = 1.0` and `ambiguity_score = 0.0`.

### Normalization Contract

The internal classification vocabulary (lowercase, hyphenated) used inside nexi-engine's intent-parser is normalized to uppercase canonical form before the Intent object is emitted from the intent-parser component. Downstream components (xnch, memory-store, audit-logger) see only the uppercase canonical form. The raw classification labels are not persisted.

---

## Contract 5: Rule-Based Option Generator

**Owner:** nexi-engine (Model Adapter)  
**Trigger:** All inference paths unavailable (vllm-primary timeout + vllm-secondary timeout + llama-cpp-python failure)  
**Output:** 3 Plan Option objects conforming to `data-contracts.md — Plan Option`

### Activation Conditions

The rule-based generator is the fallback of last resort in the Model Adapter fallback chain:

```
1. vllm-primary     → timeout > 30s OR OOM OR FATAL
2. vllm-secondary   → timeout > 45s OR unavailable
3. llama-cpp-python → any failure
4. rule-based       ← this contract
```

When activated, `generation_path` in the Decision Record is set to `RULE_BASED`.

### Option Production Rules

Options are generated by mapping `intent_class` to a fixed template set. All templates produce conservative, reversible, low-risk actions.

```yaml
QUERY:
  - action_type: "read_file"
    action_spec: {operation: "read", scope: "requested_entity_only"}
    stated_rationale: "Read-only retrieval with minimal scope"
    estimated_side_effects: []
    reversible: true

  - action_type: "list"
    action_spec: {operation: "list", scope: "requested_entity_only"}
    stated_rationale: "Non-modifying list operation"
    estimated_side_effects: []
    reversible: true

  - action_type: "analyze"
    action_spec: {operation: "analyze", scope: "requested_entity_only"}
    stated_rationale: "Analysis only, no state change"
    estimated_side_effects: []
    reversible: true

DECISION:
  - action_type: "plan"
    action_spec: {operation: "draft_plan", commit: false}
    stated_rationale: "Draft plan without commitment"
    estimated_side_effects: []
    reversible: true

  - action_type: "analyze"
    action_spec: {operation: "analyze", commit: false}
    stated_rationale: "Analysis to inform decision"
    estimated_side_effects: []
    reversible: true

  - action_type: "escalate"
    action_spec: {operation: "escalate", reason: "inference_unavailable"}
    stated_rationale: "Escalate to operator — inference unavailable for decision support"
    estimated_side_effects: []
    reversible: true

EXECUTION:
  - action_type: "backup"
    action_spec: {operation: "backup", scope: "affected_entities"}
    stated_rationale: "Backup before any execution; safe first step"
    estimated_side_effects: ["storage_write"]
    reversible: true

  - action_type: "analyze"
    action_spec: {operation: "dry_run", commit: false}
    stated_rationale: "Dry-run analysis without execution"
    estimated_side_effects: []
    reversible: true

  - action_type: "escalate"
    action_spec: {operation: "escalate", reason: "inference_unavailable"}
    stated_rationale: "Escalate to operator — inference unavailable for execution planning"
    estimated_side_effects: []
    reversible: true

ESCALATION:
  - action_type: "escalate"
    action_spec: {operation: "escalate", reason: "inference_unavailable"}
    stated_rationale: "Escalate as originally requested"
    estimated_side_effects: []
    reversible: true

  - action_type: "read_file"
    action_spec: {operation: "read", scope: "audit_log"}
    stated_rationale: "Read audit log to inform escalation context"
    estimated_side_effects: []
    reversible: true

  - action_type: "analyze"
    action_spec: {operation: "analyze", scope: "recent_decisions"}
    stated_rationale: "Analyze recent decisions for escalation context"
    estimated_side_effects: []
    reversible: true
```

### Option Object Construction

Each generated option must be constructed as a valid Plan Option:

```python
{
    "option_id": str(uuid.uuid4()),     # new UUID per option per session
    "action_type": "<from template>",
    "action_spec": {<from template>},
    "stated_rationale": "<from template>",
    "estimated_side_effects": [<from template>],
    "reversible": True,                 # always True for rule-based options
    "payload_hash": f"sha256:{sha256(json.dumps(action_spec, sort_keys=True).encode()).hexdigest()}"
}
```

`max_candidates` is set to 3 when the rule-based generator activates. The generator always produces exactly 3 options. It does not produce fewer.

### Constraints

- Rule-based options never include `action_type` values of `run_command`, `run_script`, `deploy`, `rollback`, `delete_file`, `alter_schema`, or `migrate`.
- `reversible` is always `True`.
- `estimated_side_effects` contains at most one entry.
- No model is called. No network I/O occurs during rule-based generation.

---

## Contract 6: Weight Configuration Storage

**Owner:** xnch-server (governance store)  
**Consumer:** nexi-engine (scoring, composite calculation)  
**Format:** YAML  
**Versioning:** `wc-v{major}.{minor}` (e.g., `wc-v1.0`, `wc-v2.1`)

### Schema

```yaml
version: "wc-v{major}.{minor}"   # required; semver-prefixed with "wc-"
description: "string"             # human-readable; required
intent_class: "QUERY | DECISION | EXECUTION | ESCALATION"   # required
weights:
  policy_score: float             # [0.0, 1.0]
  outcome_score: float            # [0.0, 1.0]
  risk_score: float               # [0.0, 1.0]
  context_fit_score: float        # [0.0, 1.0]
approved_at: "ISO-8601 UTC"       # set by xnch at approval time
approved_by: "string"             # operator identity
```

**Constraints:**
- `weights.policy_score + weights.outcome_score + weights.risk_score + weights.context_fit_score = 1.0`
- Each individual weight must be ≥ 0.05.

Both constraints are enforced at file load time and at approval time. xnch returns a configuration error if either is violated.

### Storage Location

```
{governance_store.path}/weights/
  QUERY-wc-v1.0.yaml
  DECISION-wc-v1.0.yaml
  EXECUTION-wc-v1.2.yaml
  ESCALATION-wc-v1.0.yaml
```

One file per `intent_class` per version. The active version for each intent class is the version last set via operator approval — it is never auto-advanced. xnch maintains an active version pointer per intent class; the pointer is updated atomically on approval and only by explicit operator action.

### Retrieval by nexi-engine

Nexi retrieves weights via the xnch governance API:

```
GET /governance/weights?intent_class=EXECUTION
```

Response:
```json
{
  "version": "wc-v1.2",
  "intent_class": "EXECUTION",
  "weights": {
    "policy_score": 0.25,
    "outcome_score": 0.30,
    "risk_score": 0.35,
    "context_fit_score": 0.10
  }
}
```

Nexi caches the response for the duration of one session. It does not re-fetch mid-session. The `weight_config_version` in the Decision Record is set to the version returned by this call.

### Versioning Rules

- **Minor version bump** (`wc-v1.0 → wc-v1.1`): weight values change within the same intent class. Backward compatible — existing Decision Records reference the version active at scoring time.
- **Major version bump** (`wc-v1.x → wc-v2.0`): schema changes (new dimension, removed dimension). Nexi must be updated to handle new dimensions before a major version is deployed.
- An approved version is never modified. The file is immutable. Updates produce a new version.

### Update Mechanism

1. Score Adapter proposes a weight adjustment (via `POST /governance/weights/propose`).
2. xnch validates the proposal: weights sum to 1.0, no dimension below 0.05.
3. xnch writes the proposed config as a pending version file.
4. Operator reviews and approves via `POST /governance/weights/approve?version=wc-v1.3`.
5. xnch sets the active pointer to the approved version.
6. Next session using that intent class picks up the new version.

No automatic promotion. Operator approval is required for every version activation.

---

## Contract 7: Session Lifecycle Contract

**Owner:** xnch-server (state authority) + KV Cache (Redis, session index)  
**Participants:** nexi-engine (session consumer), execution-runner (token consumer), memory-store (episode writer)

### Session States

```
ACTIVE      Session is processing; requests are accepted
WAITING     Session is paused awaiting actor input (CLARIFICATION_REQUIRED); TTL = 120s
EXPIRED     Session TTL has lapsed; all tokens issued in this session are invalid
COMPLETED   Execution outcome received and Episode written (Step 13–14); terminal state
FAILED      Session terminated abnormally (crash, unrecoverable error); terminal state
```

A session remains in ACTIVE state from creation through execution outcome receipt. The COMPLETED transition occurs when xnch receives the Execution Outcome at Step 13 and writes the Episode record. The verdict at Step 10 does not terminate the session — the session remains ACTIVE during execution (Steps 11–13).

State transitions:

```
              ┌─────────────────────────────────┐
              │                                 │
  [init] ──▶ ACTIVE ──▶ WAITING ──────────────▶ ACTIVE
                │         │ (120s TTL)
                │         └──────────────────▶ EXPIRED
                │
                ├──▶ COMPLETED (verdict + outcome received)
                │
                └──▶ FAILED (unrecoverable error)
```

EXPIRED, COMPLETED, and FAILED are terminal. No transitions out.

### Session Creation

A session is created at Step 2 of the system loop (actor resolution and authentication).

xnch writes the Session Context to the KV Cache immediately after creation:

```
key:   "session:{idempotency_key}"
value: <serialized Session Context>
TTL:   120s (ACTIVE state TTL)
```

The `idempotency_key` is assigned by the Input Layer at Step 1 and forwarded to xnch with the initial request. If xnch finds an existing `session:{idempotency_key}` key in the KV Cache on Step 2a, it returns the cached Session Context and skips Steps 2+. The existing session is returned as-is.

### TTL Rules

| State | TTL | Clock Start |
|-------|-----|-------------|
| ACTIVE | 120s | Session creation (Step 2) |
| WAITING | 120s | Transition to WAITING (CLARIFICATION_REQUIRED issued) |
| ACTIVE (resumed) | 120s | Transition back to ACTIVE on actor response |
| Execution token | 30s | Token issuance (Step 10) |

The session TTL and the execution token TTL are independent. A session can expire while an execution token is still valid (within its 30s window). The execution-runner validates the token against its own `exp` field — it does not query xnch for session state.

### TTL Extension

Sessions in the ACTIVE state do not have their TTL extended by activity. The 120s TTL is set at creation and not reset. If the session requires more than 120s (e.g., large context load, model timeout), it will expire.

**Exception:** When a session transitions from WAITING back to ACTIVE (actor provides clarification), xnch resets the TTL to 120s from the transition time.

### KV Cache Interaction

The KV Cache (Redis, Unix socket) is the first and only session store for deduplication and rate limiting.

**Session lookup (Step 2a):**
```
GET session:{idempotency_key}
  → HIT:  return cached Session Context; skip Steps 2+
  → MISS: proceed to actor resolution (Step 2)
```

**Rate limit check (Step 2a, after lookup miss):**
```
INCR rate:{actor_id}:{minute_bucket}
  → value ≤ limit: proceed
  → value > limit: return 429; do not create session
EXPIRE rate:{actor_id}:{minute_bucket} 60
```

`minute_bucket` is `floor(unix_time / 60)`. Rate limit values are configured in xnch-server config. Default: 10 sessions per actor per minute.

`actor_id` at this step is an unverified claim extracted from the auth token before signature verification. Rate limiting on an unverified identity is a deliberate first-line defense against request floods; verified enforcement occurs at policy evaluation after auth (Step 10).

**Session write (Step 2, after creation):**
```
SET session:{idempotency_key} <session_context_json> EX 120
```

**Session TTL reset (on WAITING → ACTIVE):**
```
EXPIRE session:{idempotency_key} 120
```

**Session deletion:** On COMPLETED or FAILED state, xnch explicitly deletes the `session:{idempotency_key}` key from the KV Cache (`DEL session:{idempotency_key}`). Do not rely on TTL expiry for terminal state cleanup — a natural TTL expiry on a completed session would allow resubmission with the same `idempotency_key` to return a stale session context.

### Session Cleanup

On TTL expiry (EXPIRED state):

1. Any `execution_token` issued in the session becomes invalid at its own `exp` (30s from issuance). Token expiry is not accelerated by session expiry.
2. The `system_state_version` pin held by xnch for this session is released.
3. No episode is written for sessions that expire before verdict (no outcome to record).
4. If an execution was dispatched and the outcome has not been received, xnch marks the execution reference as `ORPHANED` in the Decision Ledger on cleanup.

### CLARIFICATION_REQUIRED

When the intent parser returns `ambiguity_score > 0.7`:

1. xnch sets session state to `WAITING`.
2. xnch refreshes KV Cache TTL to 120s.
3. xnch returns `CLARIFICATION_REQUIRED` to the caller with `session_id` and `trace_id`.
4. Actor submits clarification via `POST /session/{session_id}/clarify` with amended input.
5. xnch transitions session back to `ACTIVE`; resets TTL; passes amended input to nexi-engine intent parser.

Only one active CLARIFICATION_REQUIRED cycle per session. If the second classification attempt also returns `ambiguity_score > 0.7`, the session transitions to FAILED.
