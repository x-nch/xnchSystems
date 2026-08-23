# Operate HITL Approvals

Audience: operator (the human in the loop). Sources:
`xnch/routes/workflows.py` approvals router, `web/src/lib/approvals/`,
[workflows architecture](../architecture/workflows-hitl.md),
[HITL UI spec](../superpowers/specs/2026-08-22-xnchsystems-hitl-dark-minimalist-design.md).

Approvals are the single queue where gated actions wait for a human decision:
workflow steps, and other producers surfaced with `producer_type`.

## Where to work the queue

**muse (preferred):** run `cd web && npm run dev` (or the deployed instance) →
approvals view on the home page; workflow builder under `/workflows`. muse talks
to xnch only through its same-origin proxy, which signs write requests with the
Hybrid-B token — you need `XNCH_GATEWAY_SECRET` set identically on both sides.

**curl:** every decide call needs gateway access
([auth model](../reference/auth-model.md#gateway-hybrid-b)):

```bash
SECRET='<XNCH_GATEWAY_SECRET>'            # placeholder — real value from env
EXP=$(( $(date +%s) + 120 ))
SIG=$(printf '%s' "$EXP" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')
TOKEN="$EXP.$SIG"

curl -s http://192.168.50.1:8001/approvals?status=pending | jq .
curl -s -X POST http://192.168.50.1:8001/approvals/<id>/decide \
  -H "Authorization: Bearer <actor-token>" \
  -H "X-Gateway-Token: $TOKEN" \
  -H "Idempotency-Key: <unique-key>" \
  -H 'Content-Type: application/json' \
  -d '{"decision": "approve"}'
```

## Decision semantics

| decision | effect |
|---|---|
| `approve` | producer-dependent: executor off ⇒ step **DONE** immediately; executor on ⇒ step **APPROVED** for nexi to claim ([lease semantics](../architecture/workflows-hitl.md#executor-claim-lease-semantics-nexiworkflowexecutorpy)) |
| anything else | approval **REJECTED**, produced step cancelled |

- `Idempotency-Key` replays are safe: same key returns the original result.
- Rejecting cancels the linked step/run (`CANCELLED`), recorded in
  `snapshot_json`.
- Every decision is audit-logged with actor + timestamp.

## Verdict-path HITL (decision pipeline)

The LangGraph interrupt variant surfaces at
`POST /governance/pipeline/invoke` → interrupt → resume after your decision;
mode/risk governed by `XNCH_HITL_EXECUTION_MODE` /
`XNCH_HITL_RISK_THRESHOLD`. Classic verdict flow (propose → `/verdict`) is
always authoritative regardless of UI.

## Checklist when something looks stuck

1. Queue empty but workflow not progressing? Check executor is enabled on both
   sides (`XNCH_WORKFLOW_EXECUTOR_ENABLED`, `NEXI_WORKFLOW_EXECUTOR_ENABLED`)
   and nexi logs for claim errors.
2. Steps stuck `CLAIMED`? Leases expire by TTL (default 120 s) — stale claims
   auto-reclaim; no manual release exists.
3. 401/403 on decide? Secret mismatch or expired token — re-mint.
