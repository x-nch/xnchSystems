# Runbook — Rollback

Two distinct rollback scenarios. The authoritative, step-complete procedure is
the immutable migration record — **[infra/no-k3s/MIGRATION.md §Rollback](../../infra/no-k3s/MIGRATION.md#rollback-plan)**
— linked here rather than duplicated.

## 1. Service-level rollback (stay on no-k3s)

```bash
# Node B: stop inference + engine
sudo systemctl stop nexi.service vllm-ornith.service
# Node A: stop control plane + jobs
cd ~/xnchSystems/infra/no-k3s/node-a
sudo systemctl stop xnch.service consolidation.timer consolidation.service
docker compose down
```

Then fix forward and re-run [e2e smoke](e2e-smoke.md). Config-level reverts
(nexi URL defaults etc.) are tabulated in MIGRATION.md §"Restore nexi config.py
defaults".

## 2. Regime rollback (return to k3s)

Full procedure: MIGRATION.md §Rollback (stop services → `systemctl start k3s`
→ `kubectl apply -f deploy/k8s/` → verify pods). Note the legacy manifest tree
is `infra/k8s/**` in this repo and describes the retired regime (Gemma/mem0/zep
era) — expect drift if you ever execute this path.

## Data safety

Before either path: back up Postgres volumes (`pgdata`, `langfuse-pgdata`) and
`~/.xnch/` (keys, audit ledger, SQLite stores, graph.kuzu).
