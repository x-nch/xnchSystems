# Security Architecture

XNCH and Nexi form a two-layer orchestration system where one process (xnch) evaluates and gates every action a second process (nexi) can take. An attacker who compromises one layer cannot freely access the other. This document covers the threat model, trust system, injection defenses, memory protection, and token policies that enforce that boundary. If you are integrating a new agent, adding a route, or debugging a 403, this is the starting point.

---

## Threat Model

The system is designed around three primary attack surfaces: rogue agents, prompt injection, and memory poisoning. Each is addressed by a defense layer that operates independently, so a failure in any one layer does not expose the system.

### Rogue Agents

An external or compromised agent could attempt to execute actions, read memory, or trigger jobs without authorization. The defense is a cascading system of identity resolution, trust level assignment, and capability gating. Every incoming request carries an `X-Actor-Role` header. The system maps that role to a numeric trust level, derives a set of boolean capabilities, and enforces those capabilities at the route level. An actor with no explicit mapping — or the reserved name `"external"` — lands at trust level 1 with zero capabilities. It cannot write memory, read memory, trigger jobs, modify policies, or access perception.

### Prompt Injection

An attacker crafts a chat message that attempts to override the system prompt, reassign the agent's role, or instruct it to disregard prior instructions. The defense is `scan_input()` in `xnch/security/injection_guard.py`, which applies nine compiled regex patterns to every incoming message before any context assembly or LLM call occurs. If any pattern matches, the request is rejected at the HTTP layer with a 400 response and the message "Input rejected by injection guard." No context is loaded, no LLM call is made, and no memory is written.

### Memory Poisoning

An attacker writes malicious data to episodic memory. That data would be retrieved as context in future sessions and could influence downstream decisions, including policy evaluation or job execution. The defense has two gates in `validate_memory_write()`: the content is first scanned by the same injection guard, and then the actor's trust level must be at least TRUSTED_AGENT (3). If either check fails, the write is rejected. The quarantine infrastructure provides an alternative path: instead of silently dropping blocked content, it can be preserved in PostgreSQL for manual review.

---

## Trust Levels

Trust levels are integer-valued constants defined in `xnch/security/trust_model.py`. Five levels in ascending order:

| Level | Value | Meaning |
|---|---|---|
| UNTRUSTED | 1 | Unknown or explicitly external actors. Default for any unmapped role. |
| EXTERNAL_AGENT | 2 | Third-party agent integrations (future). Read-only — no writes or job triggers. |
| TRUSTED_AGENT | 3 | Known system agents: opencode, perception_daemon, consolidation_job. Can write memory and trigger jobs. |
| OWNER | 4 | The human operator. Can write and read all memory, trigger jobs, and access perception. |
| SYSTEM | 5 | The nexi engine itself. Full capabilities including policy modification. |

### Actor-to-Trust Mapping

Every actor identity resolves to exactly one trust level via `ACTOR_TRUST_MAP`. The fallback in `get_trust_level()` returns UNTRUSTED for any role not present in the map. There is no way to escalate without an explicit entry.

| Actor | Trust Level |
|---|---|
| nexi | SYSTEM (5) |
| admin | OWNER (4) |
| operator | OWNER (4) |
| agent | TRUSTED_AGENT (3) |
| viewer | EXTERNAL_AGENT (2) |
| opencode | TRUSTED_AGENT (3) |
| perception_daemon | TRUSTED_AGENT (3) |
| consolidation_job | TRUSTED_AGENT (3) |
| external | UNTRUSTED (1) |
| *any unmapped string* | UNTRUSTED (1) |

### Capability Grid

Capabilities are derived from trust level in `xnch/security/actor_sandbox.py`. Every route that gates on a capability calls `get_capabilities(actor_role)` and checks the appropriate boolean field on the returned `ActorCapabilities` dataclass.

| Capability | SYSTEM | OWNER | TRUSTED_AGENT | EXTERNAL_AGENT | UNTRUSTED |
|---|---|---|---|---|---|
| can_write_memory | Yes | Yes | Yes | No | No |
| can_read_all_memory | Yes | Yes | No | No | No |
| can_trigger_jobs | Yes | Yes | Yes | No | No |
| can_modify_policies | Yes | No | No | No | No |
| can_access_perception | Yes | Yes | No | No | No |

### Enforcement Mechanisms

Trust is enforced through two mechanisms that operate at different layers.

The `@requires_trust(minimum)` decorator is applied to FastAPI route handlers. It reads the `X-Actor-Role` header from the incoming request, resolves it to a trust level against `ACTOR_TRUST_MAP`, and returns HTTP 403 if the level is below the required minimum. If no `Request` object is available in the call context, it returns HTTP 500 — a hard fail rather than a silent default.

The capability check runs at the route handler level. For example, `POST /memory/write` in `xnch/routes/memory.py` calls `get_capabilities(body.actor_role)` and returns 403 if `can_write_memory` is false. This is a defense-in-depth layer on top of the trust-level decorator — even if a route's trust gate were bypassed, the capability check would still block unauthorized access.

Capabilities are not directly configurable per actor. They are derived from trust level, and the trust level is determined by the actor's presence in `ACTOR_TRUST_MAP`. To grant a new capability to an actor, the actor's trust level must be raised, which brings all capabilities at that level.

---

## Injection Guard

The injection guard lives in `xnch/security/injection_guard.py`. It maintains nine compiled regular expression patterns that cover the common categories of prompt injection and jailbreak attempts.

### The Nine Patterns

Each pattern is compiled with `re.I` (case-insensitive) and applied via `re.search`:

1. `ignore previous instructions` — overriding the system prompt.
2. `forget your (system prompt|character|identity)` — memory wipe attempts targeting the system prompt, character definition, or identity.
3. `you are now` — role reassignment without the agent's consent.
4. `your new (instructions|role|persona)` — instruction override that attempts to replace the agent's operating parameters.
5. `disregard.*above` — context disregard that tries to make the agent ignore preceding instructions.
6. `act as (?!(Nexi|nexi))` — impersonation with a negative lookahead that explicitly allows "act as Nexi" but blocks "act as ChatGPT" or any other role.
7. `jailbreak` — the keyword itself, a common jailbreak signal.
8. `DAN mode` — the DAN (Do Anything Now) jailbreak variant.
9. `pretend (you|that)` — pretense-based override attempts.

### scan_input()

`scan_input(text, event_log=None)` takes a string and an optional `EventLog` instance. It returns an `InjectionResult` dataclass with three fields:

- **`is_clean`**: True only if no patterns matched (`risk_score == 0.0`). Any match, even a single one, sets this to False.
- **`matched_patterns`**: A list of the pattern text values that matched (empty if clean).
- **`risk_score`**: `len(matched_patterns) / len(INJECTION_PATTERNS)`, ranging from 0.0 to 1.0.

### Blocking vs Logging Thresholds

The blocking condition is `not is_clean` — if any single pattern matches, the request is blocked. There is no scoring threshold for blocking.

The logging threshold is `risk_score > 0.1`. Because there are exactly 9 patterns, a single match produces a risk score of 1/9 = 0.11, which exceeds 0.1. This means every match also triggers a WARNING-level event log entry (provided an EventLog instance was passed). The event payload includes the matched patterns, the computed risk score, and the first 200 characters of the input text.

### What Gets Scanned

Every incoming chat message passes through `scan_input` before any context assembly or LLM call. This runs at the HTTP layer in the route handler, before the message is written to memory or forwarded to Nexi. The scan also runs on memory writes (see below). The ordering is intentional: reject early, before any expensive or irreversible operation.

---

## Memory Writes and Quarantine

Memory writes are protected by `validate_memory_write()` in `xnch/security/memory_guard.py`. The function performs two checks in sequence:

1. **Injection scan**: calls `scan_input(content)`. If the content fails the scan, the function returns `(False, "Content failed injection scan")`. No write occurs.

2. **Trust check**: if the actor's trust level is below TRUSTED_AGENT (value < 3), the function returns `(False, "Trust level N (actor) cannot write to episodic store directly")`. Level 1 (UNTRUSTED) and level 2 (EXTERNAL_AGENT) actors cannot write to episodic memory by any route.

If both checks pass, the function returns `(True, None)` and the write proceeds normally.

### Quarantine Store

The quarantine infrastructure in `QuarantineStore` (`xnch/memory/quarantine_store.py`) provides an alternative to hard rejection. Instead of silently dropping blocked content, the system can preserve it in a PostgreSQL table for manual review. The table schema:

```
quarantine_memories (
  id UUID PRIMARY KEY,
  memory_type TEXT,
  raw_text TEXT,
  summary TEXT,
  importance REAL DEFAULT 1.0,
  quarantine_reason TEXT,
  quarantined_by TEXT,
  original_actor_role TEXT,
  original_trust_level TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  released_at TIMESTAMPTZ,
  released_by TEXT
)
```

The `QuarantineStore` exposes three operations:

- **`quarantine(memory_type, raw_text, summary, quarantine_reason, quarantined_by, original_actor_role, original_trust_level, importance=1.0)`**: Inserts a row into the `quarantine_memories` table. The `id` is a generated UUID; `created_at` defaults to the current timestamp; `released_at` and `released_by` are null.

- **`release_to_memory(id, released_by)`**: Sets `released_at` to the current timestamp and `released_by` to the provided actor. Returns True if a row was actually updated. This is the approval path: a human operator reviews the quarantined content and decides it is safe to admit.

- **`list_quarantined()`**: Returns all rows where `released_at IS NULL`, ordered by `created_at` descending. This is the review queue.

### Current State

As of this writing, `validate_memory_write` returns a boolean and a reason string. The caller in `nexi_gateway.py` logs a warning when a write is blocked but does not currently call `quarantine_store.quarantine()`. The quarantine infrastructure exists and is tested but is not wired into the production path. A future change would route blocked writes to quarantine instead of logging and dropping them, giving the human operator a chance to review and release.

---

## JWT Token System

The system uses two distinct token types for different purposes: execution tokens for authorization verification across the xnch/nexi boundary, and bearer tokens for client-to-server authentication.

### Execution Tokens (RS256)

Execution tokens are asymmetric RSA 2048-bit JWTs signed by xnch's private key. The key pair is auto-generated on first boot and stored at `~/.xnch/keys/` — private key at `private.pem`, public key at `public.pem`. Nexi reads the public key path from `NEXI_XNCH_PUBLIC_KEY_PATH` to verify tokens.

Tokens are issued as the final step of the verdict flow: `POST /verdict` produces a token only when the verdict is ALLOW or BLOCK. The execution layer must present this token to prove that the action was evaluated and approved by xnch.

The token payload contains:

- `iss`: "xnch"
- `sub`: "execution_token"
- `jti`: UUID, unique per token — used for replay protection
- `iat`, `exp`: issuance and expiry timestamps
- `role`: the actor's trust level name (e.g., "OWNER")
- `session_id`, `decision_id`, `trace_id`: correlation identifiers
- `actor_id`, `actor_role`: the original actor identity
- `action_type`, `entity_class`: the evaluated action
- `policy_version`, `system_state_version`: version pins for audit
- `token_ttl_ms`: token TTL in milliseconds
- `trust_level`: numeric trust level value

TTL varies by trust level. Higher trust earns longer validity:

| Trust Level | Value | Token TTL |
|---|---|---|
| SYSTEM | 5 | 7 days (604,800 s) |
| OWNER | 4 | 1 day (86,400 s) |
| TRUSTED_AGENT | 3 | 1 hour (3,600 s) |
| EXTERNAL_AGENT | 2 | 30 minutes (1,800 s) |
| UNTRUSTED | 1 | No token issued |

UNTRUSTED actors never receive an execution token. If the verdict system reaches token issuance for an UNTRUSTED actor, it returns an error rather than issuing a credential.

### Bearer Tokens (HS256)

Bearer tokens are symmetric JWTs used for client-to-server authentication at the HTTP layer. The shared secret is configured via `XNCH_AUTH_SECRET`.

`verify_bearer(authorization)` in `xnch/auth/token_verifier.py` accepts two formats:

- **`actor:<actor_id>`**: A plain-text actor reference. This is accepted only in development mode. It exists to simplify local testing without JWT generation infrastructure.
- **`Bearer <hs256-jwt>`**: A standard Bearer token. The JWT must have a `sub` claim containing the actor_id. The token is verified using the shared HS256 secret.

The function returns the actor_id string on success, `None` on failure (malformed header, expired token, invalid signature). There is no distinction in the return value between a bad signature and an expired token — both produce `None`, and the caller sees a 401.

### Token Replay Protection

Execution tokens include a `jti` (JWT ID) that is unique per token. An in-memory `_JtiSeenSet` tracks all seen jti values along with their expiry timestamps. The `consume(jti, exp)` method checks whether a jti has been seen before:

- If the jti is new (not in the set), it is recorded and the method returns True.
- If the jti has already been seen (a replay attempt), the method returns False.

Expired entries are purged from the set on every call to `consume`. This keeps the set bounded to the lifetime of the longest-lived token (7 days for SYSTEM tokens), though in practice most entries are short-lived.

The implementation is process-local. If the server restarts, the seen-set is lost. For distributed deployments with multiple xnch instances behind a load balancer, a Redis-backed seen-set would be necessary to prevent replay attacks across instances. That is not yet implemented.

---

## Governance Store

The GovernanceStore (`xnch/auth/governance.py`) is backed by SQLite and manages actors with their roles and JSON capability sets. Four actors are bootstrapped on first start:

| Actor | Role | Purpose |
|---|---|---|
| admin | ADMIN | Full system administration |
| operator | OPERATOR | Day-to-day operations |
| viewer | VIEWER | Read-only access |
| agent | AGENT | Programmatic agent access |

Actors can be upserted via `POST /governance/actors`. This is separate from the trust-level system — governance actors are for API-level access control, while trust levels control what specific operations (memory writes, job triggers, policy modifications) an authenticated actor can perform.

---

## Putting It Together: Request Lifecycle

A request arriving at the API server passes through these security layers in order:

1. **Bearer verification** (`verify_bearer`): Extract and validate the actor identity from the Authorization header. If the token is invalid or expired, return 401 immediately.

2. **Trust check** (`@requires_trust` decorator): Map the actor role to a trust level. If the route requires minimum trust level N and the actor is below it, return 403.

3. **Capability check** (route-specific): For guarded operations (memory writes, job triggers, policy modifications), call `get_capabilities` and check the specific boolean. Return 403 if the capability is absent.

4. **Injection scan** (`scan_input`): For chat messages and memory writes, scan the content against the nine patterns. If any match, return 400 with no further processing.

5. **Memory write validation** (`validate_memory_write`): For episodic memory writes, run the injection scan and trust level check in sequence. Reject with a descriptive reason if either fails.

6. **Verdict flow and execution token issuance**: If the request reaches the verdict endpoint and produces an ALLOW or BLOCK decision, issue an RS256 execution token with the appropriate TTL. The execution layer verifies this token before acting on the verdict.

This layered approach means a failure at any stage stops processing before reaching the next. No LLM call, no memory write, no policy change, and no job trigger occurs unless all relevant gates pass.
