# xnch

---
tags:
  - #component
  - #xnch
  - #policy
---

The control plane. Single enforcement point for all action proposals, memory mutations, and execution commands. Every other component in the system — Nexi, the execution layer, agents — interacts with the world only through xnch.

Architecture classification: synchronous, stateful, deterministic gateway with async audit emission.

For internal architecture and design principles, see [[xnch-control-plane.md]].

---

## Related

- [[xnch-control-plane.md]]
- [[data-contracts.md]]

---

## Starting xnch

```bash
# Start xnch server (default: port 8100)
xnch-server --config ~/.xnch/config.yaml

# Health check
curl http://localhost:8100/health
```

xnch must be running before Nexi, the execution runner, or any agent can operate. The startup sequence is:

```
vllm-primary → memory-store → xnch-server → nexi-engine → execution-runner → audit-logger
```

---

## Interface Surface

xnch exposes six interfaces. All are required — partial requests are rejected.

### POST /verdict

Primary evaluation interface. Accepts a structured action proposal, evaluates it against active policy, and returns a deterministic verdict.

**Request:**
```json
{
  "request_id": "uuid",
  "actor": {
    "id": "string",
    "claimed_role": "string"
  },
  "action": {
    "type": "QUERY | MUTATE | EXECUTE | MEMORY_WRITE | POLICY_CHECK",
    "target": "string",
    "payload_hash": "sha256:...",
    "payload": {}
  },
  "context": {
    "session_id": "uuid",
    "prior_request_ids": ["uuid"],
    "nexi_reasoning_ref": "uuid"
  }
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "verdict": "ALLOW | BLOCK | MODIFY | DEFER",
  "verdict_reason": "string",
  "policy_refs": ["policy_id"],
  "modified_action": null,
  "execution_token": "signed_jwt | null",
  "token_ttl_ms": 30000,
  "audit_ref": "uuid"
}
```

Verdicts are never cached. Every proposal is a fresh evaluation — system state may change between calls.

### GET /policy/check

Dry-run policy evaluation. Returns a verdict without issuing an execution token and without writing a full audit event (emits a lighter `policy_check` trace). Used by Nexi for parallel option screening before final verdict submission.

```bash
curl -X GET http://localhost:8100/policy/check \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -d '{"action": {...}, "session_id": "...", "system_state_version": "..."}'
```

### POST /memory/read

Governed memory query. xnch applies read policy against the actor's capability scope before returning content. Nexi cannot query memory directly.

### POST /memory/write

Governed memory mutation. xnch validates write policy and schema before committing. All writes are evaluated through the verdict path — a memory write is an action type like any other.

### GET /system/state

Returns current system state version, active policy version, and any active holds or overrides. Nexi must call this at session initialization and pin the version. If the version changes mid-session, xnch rejects the final verdict with `STALE_SESSION`.

### POST /audit/query

Actor-scoped access to audit history. xnch filters records to what the requesting actor is authorized to see. This is the path for forensic access to decision reasoning — not Nexi's output.

---

## Verdicts

| Verdict | Meaning | Effect |
|---------|---------|--------|
| `ALLOW` | Action passes all policies | Execution token issued |
| `BLOCK` | Action violates policy | Request terminated with structured rejection |
| `MODIFY` | Action passes with required changes | Action spec rewritten by xnch; token issued for modified spec |
| `DEFER` | Action requires secondary authorization | Action placed in hold queue; no token issued |

`MODIFY` rewrites the action spec inside xnch before issuing the token. The execution layer receives the modified spec — it never sees the original.

---

## Execution Tokens

Execution tokens are xnch-signed JWTs with a configurable TTL (default: 30,000ms). The execution layer validates the token signature independently — it does not trust Nexi's claim that xnch approved the action.

If a token expires before dispatch (scoring or simulation took too long), the execution layer rejects with `TOKEN_EXPIRED`. Nexi resubmits to `/verdict` with the same `decision_id`. xnch re-evaluates and issues a new token. The `idempotency_key` on `decision_id` prevents duplicate audit records.

---

## Policy Enforcement

Policies are declarative rules stored in xnch's governance store. They are versioned, immutable once deployed, and auditable. No runtime mutation.

Policy types:
- **Hard blocks**: Non-negotiable rejections (e.g., `ml.deploy.gpu_node_only`)
- **Conditional allows**: Require context evaluation (e.g., resource check conditions)
- **Modifications**: Force specific parameter values before allowing (e.g., `ml.deploy.max_replicas_3`)
- **Defers**: Require secondary authorization (e.g., high-risk actions by agent actors)
- **Rate/quota**: Limits per actor or entity class within time windows

Policy files:
```
~/.xnch/policies/
├── default.yaml      # system defaults
└── custom.yaml       # operator-defined rules
```

---

## Memory Interaction

xnch is the sole write authority for governed memory. The flow:

```
Nexi → POST /memory/read  → xnch applies read policy → returns context manifest
Nexi → POST /memory/write → xnch validates schema + write policy → commits or rejects
Execution Layer → POST /execution/outcome → xnch writes episode to Episodic Store
```

---

## Session Lifecycle

```python
# 1. Session initialization — called once per user request
POST /session/init
# xnch: verifies auth token, resolves actor → role, pins system_state_version
# Returns: session_context forwarded to Nexi

# 2. Mid-session interactions (memory reads, policy dry-runs)
# All carry session_id and system_state_version

# 3. Final verdict
POST /verdict
# xnch: re-verifies state version match, runs authoritative policy check,
# emits audit record synchronously, issues execution token

# 4. Execution outcome (async)
POST /execution/outcome
# xnch: writes episode, triggers Nexi callback
```

---

## Configuration

```yaml
xnch:
  host: localhost
  port: 8100

  keys:
    private: ~/.xnch/keys/private.pem
    public: ~/.xnch/keys/public.pem

  token_ttl_ms: 30000

  governance_store:
    path: ~/.xnch/data/policy.db

  policy_paths:
    - ~/.xnch/policies/default.yaml
    - ~/.xnch/policies/custom.yaml

  audit:
    event_log:
      path: ~/.xnch/audit/events.jsonl
      rotation: daily
      retention: 30
    decision_ledger:
      path: ~/.xnch/audit/decisions.jsonl
      retention: 365
```

---

## Error Responses

| Code | Meaning |
|------|---------|
| `401` | Auth token invalid or missing |
| `403` | Actor lacks capability for this action type |
| `409` | `STALE_SESSION` — system state version mismatch |
| `422` | Malformed request — required field missing |
| `503` | xnch governance store unavailable |

All errors return a structured body with `error_code`, `message`, and `request_id`.
