# Runbook — E2E Smoke Test

Source: `infra/no-k3s/e2e-test.sh`. Run from **Node A** after any stack change.

```bash
cd ~/xnchSystems/infra/no-k3s
./e2e-test.sh
```

Requires an `operator` actor and a valid `XNCH_AUTH_SECRET` in the environment.
The script checks, in order:

1. Health of all four core services — xnch :8001, litellm :4000,
   vLLM :8082 (Node B), nexi :8000 (Node B).
2. LiteLLM model registration for `ornith`.
3. Session init through the full pipeline (`POST /session/start` with
   `system_state_version`/`policy_version` matching xnch `/system/state`).
4. Both chat endpoints respond.

Interpreting failures:

| Failing stage | Likely cause | Fix |
|---|---|---|
| xnch health | redis/pg down or bridge misconfig | [restart-node-a](restart-node-a.md) |
| litellm model missing | routing yaml wrong served name | must be `openai/ornith-1.0-35b` |
| vLLM/nexi unreachable | Node B asleep or stopped | [wake](wake-node-b.md) then [restart-node-b](restart-node-b.md) |
| session init 409 | state/policy version mismatch | services restarted out of order; restart nexi after xnch |

For repo-level test verification instead of live-stack smoke, see
[tests reference](../reference/tests.md) (mind the three known pre-existing
failures — they are not regressions).
