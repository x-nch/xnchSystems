# Deploy Node A (gate7 — control plane)

Audience: ops. Sources: `infra/no-k3s/node-a/**`, `infra/no-k3s/MIGRATION.md`
§1, [topology](../architecture/topology.md). Node A runs Docker Compose
(stateful services) + systemd (`xnch`, consolidation timer, tailscale funnel).

## Prerequisites

- Docker running; systemd available.
- `~/.xnch/xnch.env` created from `infra/no-k3s/shared/.env.example`
  (POSTGRES_PASSWORD, LANGFUSE_*, LITELLM_MASTER_KEY, XNCH_AUTH_SECRET,
  XNCH_GATEWAY_SECRET if muse is used).
- Static IP `192.168.50.1` on the node-to-node link.

## Bring-up

```bash
cd ~/xnchSystems/infra/no-k3s/node-a
./start-node-a.sh --wake-node-b --wait-node-b
```

Flags: `--install` (copy systemd units), `--skip-docker`,
`--wake-node-b` (WoL + wait for ping), `--wait-node-b` (block until vLLM
:8082 answers), `--no-litellm-restart`.

Manual equivalent:

```bash
docker compose up -d
```

Unit install (exact files):

```bash
sudo cp systemd/xnch.service systemd/consolidation.service systemd/consolidation.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xnch.service consolidation.timer
```

## Verify

```bash
curl -sf http://localhost:8001/health              # xnch
curl -sf http://localhost:4000/health/liveliness   # litellm (unauth probe)
curl -sf http://localhost:3000/api/public/health   # langfuse v2
redis-cli ping                                     # redis
pg_isready -h localhost -p 5432                    # pgvector store
systemctl list-timers | grep consolidation         # timer active
./../e2e-test.sh                                   # full smoke (needs operator actor)
```

## Ops gotchas (from deployment notes)

- **Pin langfuse to v2** (`langfuse/langfuse:2`) — v3 needs ClickHouse. v2 also
  requires a valid `NEXTAUTH_URL`; health path is `/api/public/health`.
- langfuse/litellm images ship no `curl` — healthchecks use wget/python and the
  unauth litellm `/health/liveliness`.
- litellm `/health` needs the master key and reports upstreams unhealthy until
  Node B is up — expected, not a proxy failure.
- litellm routing (`shared/litellm-routing.yaml`) must target the **vLLM served
  name** `openai/ornith-1.0-35b`; `qwen3-xml` is only the public alias.
- Do **not** enable `perception.service` or `vault-indexer.service`: no code
  entrypoints exist (broken ExecStarts). Deferred by design.
- `tailscale-funnel-xnch.service` requires `tailscaled` + xnch before start.

## Related

- Restart procedures: [restart-node-a](../runbooks/restart-node-a.md)
- Rollback to k3s: MIGRATION.md §Rollback → [rollback runbook](../runbooks/rollback.md)
- Deploy Node B next: [deploy-node-b](deploy-node-b.md)
