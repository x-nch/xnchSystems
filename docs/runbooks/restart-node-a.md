# Runbook — Restart Node A services

Node A = gate7 (`192.168.50.1`), Docker Compose (stateful) + systemd.
Sources: `infra/no-k3s/node-a/**`, [deploy guide](../guides/deploy-node-a.md).

## xnch (:8001)

```bash
sudo systemctl restart xnch.service
curl -sf http://localhost:8001/health        # includes redis + mcp_bridge summary
journalctl -u xnch.service -n 50 --no-pager  # on failure
```

xnch startup spawns the MCP bridge children (`crg_`, `am_`, `doc_*`)
from `~/.xnch/mcp-servers.yaml`; a failed child degrades to fewer tools, it
does not block boot ([bridge lifecycle](../architecture/mcp-bridge.md#lifecycle--health)).

## Consolidation

```bash
sudo systemctl restart consolidation.timer consolidation.service
systemctl list-timers | grep consolidation   # next run time
curl -s -X POST http://localhost:8001/admin/consolidate -H "Authorization: Bearer <actor-token>"   # manual trigger
```

## Docker stack (litellm, langfuse ×2, postgres, redis, searxng)

```bash
cd ~/xnchSystems/infra/no-k3s/node-a
docker compose ps
docker compose restart litellm               # single service
docker compose up -d                         # reconcile after compose edits
```

Health:

```bash
curl -sf http://localhost:4000/health/liveliness   # litellm unauth probe (/health needs master key)
curl -sf http://localhost:3000/api/public/health   # langfuse v2
redis-cli ping
pg_isready -h localhost -p 5432                    # main store
pg_isready -h localhost -p 5433                    # langfuse store
```

## Full Node A bounce

Scripted: `./start-node-a.sh --wake-node-b --wait-node-b`
(boot order, WoL, and vLLM wait handled —
[boot sequence](../architecture/topology.md#boot-order)).

Manual order matters — stateful first:

1. `docker compose up -d` (postgres, redis, langfuse, litellm, searxng)
2. `sudo systemctl start xnch.service`
3. `sudo systemctl start consolidation.timer tailscale-funnel-xnch.service`
4. Wake Node B if needed: [wake runbook](wake-node-b.md)

## Tailscale funnel

```bash
sudo systemctl restart tailscale-funnel-xnch.service
# Requires tailscaled.service + xnch.service (unit enforces Requires=)
```

## Deferred units — do not enable

`perception.service`, `vault-indexer.service`: no code entrypoints exist;
units ship with broken ExecStarts intentionally parked. See
[deploy gotchas](../guides/deploy-node-a.md#ops-gotchas-from-deployment-notes).
