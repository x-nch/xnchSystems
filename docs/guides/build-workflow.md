# Build & Run a Workflow

Audience: operator/dev. Sources: `xnch/routes/workflows.py` models,
`web/src/lib/workflows/`, executor in `nexi/workflow/executor.py`. Field-level
schemas: read the Pydantic models beside each handler (this page shows shape,
code is contract).

## 1. Enable the executor mode (optional but recommended)

```bash
# Node A ~/.xnch/xnch.env
XNCH_GATEWAY_SECRET='<shared-secret>'          # placeholder
XNCH_WORKFLOW_EXECUTOR_ENABLED=true

# Node B ~/.xnch/nexi.env
NEXI_WORKFLOW_EXECUTOR_ENABLED=true            # claims APPROVED steps every 5s
```

With the flag off (v1 semantics), approving a step marks it DONE immediately —
useful for dry-run drills.

## 2. Create a workflow

```bash
curl -s -X POST http://192.168.50.1:8001/workflows \
  -H "Authorization: Bearer <actor-token>" \
  -H "X-Gateway-Token: <minted>" \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "nightly-report",
        "steps": [
          {"name": "gather", "payload": {"kind": "memory_read", "...": "..."}},
          {"name": "publish", "payload": {"kind": "chat", "...": "..."}}
        ]
      }' | jq .
```

Gated steps are flagged for approval at creation; they land in the approvals
queue as `AWAITING_APPROVAL`.

## 3. Start a run

```bash
curl -s -X POST http://192.168.50.1:8001/workflows/<workflow_id>/run \
  -H "Authorization: Bearer <actor-token>" \
  -H "X-Gateway-Token: <minted>" | jq .
```

## 4. Approve

muse queue or curl — full walkthrough:
[operate HITL](operate-hitl.md). After approval the step is `APPROVED`
(executor on) and nexi's executor picks it up within its poll interval.

## 5. Watch execution

- `GET /workflows/runs` — run history with statuses.
- `GET /workflows/<id>` — current step states.
- Executor loop: claim (`lease_owner=nexi-wf-executor`, TTL 120 s) → run one
  pipeline pass → report outcome `SUCCESS|PARTIAL|FAILURE`. FAILURE retries
  with backoff to `max_retries`, then FAILED; leases release implicitly by
  expiry, so crashed executors self-heal.

## 6. muse builder alternative

The `/workflows` page in muse creates definitions and starts runs through the
same API (signed by the proxy) — use it when you want forms instead of curl.

## Troubleshooting

| Symptom | Check |
|---|---|
| create/run returns 401/403 | missing/expired `X-Gateway-Token`, secret mismatch |
| steps never leave APPROVED | nexi executor disabled, poll logs, cross-node URL |
| run FAILED immediately | a hard-failed step (REJECTED/FAILED) fails the whole run |
| stale CLAIMED forever | shouldn't happen — lease expiry reclaims; verify TTL knobs |
