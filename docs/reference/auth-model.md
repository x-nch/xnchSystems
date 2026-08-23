# Auth Model

Sources: `xnch/auth/{keys,token}.py`, `xnch/security/{trust_model,gateway_token,injection_guard,memory_guard}.py`,
`web/src/app/api/gateway/[...path]/route.ts`,
[workflows backend spec §4](../superpowers/specs/2026-08-22-workflows-backend-design.md).

Four distinct credential systems; do not conflate them.

## 1. API actor tokens — HS256 shared secret

Callers of xnch :8001 authenticate as an **actor** with
`Authorization: Bearer <token>`:

- A raw shared-secret bearer (`XNCH_AUTH_SECRET`) or an HS256 JWT signed with it
  carrying `sub = actor_id`. Verified constant-time server-side.
- Actor roles map to trust levels which bound tool tiers
  ([tier matrix](../architecture/mcp-bridge.md#actor--tier-model)):
  `viewer`/`external` ≤ T0_READ; `opencode`/`agent`/`perception_daemon`/
  `consolidation_job` ≤ T1_WRITE; `operator`/`admin` and `nexi`(SYSTEM) ≤ T2_EXEC.
- Session init additionally enforces dedup, per-minute rate limiting
  (`XNCH_RATE_LIMIT_PER_MINUTE`) and `system_state_version`/`policy_version`
  agreement with `GET /system/state` (409 on mismatch).

## 2. Execution tokens — RS256 asymmetric

Issued by xnch on ALLOW verdicts (`auth/token.py`): RS256 over a 2048-bit keypair
under `~/.xnch/keys/`, TTL `XNCH_TOKEN_TTL_MS` (30 s default), **jti replay
protection**. Enforcement point is xnch itself on `/execution/*`; nexi forwards
the token unchanged — `NEXI_XNCH_PUBLIC_KEY_PATH` (`~/.xnch/keys/public.pem`)
is provisioned in nexi config but no JWT decode exists in nexi code today
(code-verified 2026-08-23).

## 3. Gateway Hybrid-B — short-lived HMAC (workflows/approvals writes)

Gates state-changing requests to `/workflows/*` and `/approvals/*` so a
client-forged role header alone cannot decide approvals.

- Token format: `<expiry_epoch>.<hex(hmac_sha256(secret, expiry_epoch))>`,
  TTL 300 s, constant-time compared (`security/gateway_token.py`).
- Header: `X-Gateway-Token`.
- Secret: `XNCH_GATEWAY_SECRET` — shared between xnch and the muse proxy.
  **Empty ⇒ gate open (dev/test only).**
- Alternative for service callers (nexi executor): present the shared service
  key directly (`verify_service_key`, exact compare).
- Muse mints per-request: non-GET to `workflows|approvals` prefixes gets a fresh
  token from its `XNCH_GATEWAY_SECRET`; browser never sees the secret.
- GET/HEAD/OPTIONS are ungated.

## 4. MCP tool tiers — enforced at invocation

Every tool call (native or bridged) checks `tool.allowed_actors` **and**
`tool.tier ≤ max_tier_for_role(actor)`; every call is audited as `TOOL_CALL`
([bridge details](../architecture/mcp-bridge.md)).

## Input/write guards

- `injection_guard.scan_input` runs before chat assembly.
- `memory_guard.validate_memory_write` gates all memory writes.
- Exec/fs side-effects go through policy files
  (`infra/no-k3s/shared/exec-policy.yaml`, `fs-policy.yaml`) — allowlisted
  prefixes, destructive-substring denial, cwd lock, timeouts
  ([config files](config-files.md)).

## Header quick reference

| Header | Where required | Value |
|---|---|---|
| `Authorization` | most xnch routes | `Bearer <HS256 token or secret>` |
| `X-Gateway-Token` | `/workflows/*`,`/approvals/*` writes | `<expiry>.<hmac>` |
| `Idempotency-Key` | `POST /approvals/{id}/decide` | client-chosen unique key |
| `X-Actor-Id` | step outcome calls | acting actor (default `nexi`) |
