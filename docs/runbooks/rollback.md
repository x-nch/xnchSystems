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

## 3. Phase 2 memory-service rollback (embedded ↔ remote)

The memory-service extraction (Phase 2) introduces an instant, one-command
rollback via the `XNCH_MEMORY_EMBEDDED` flag. No service reinstall required.

**Remote → Embedded (instant rollback):**
```bash
# Node A: flip the flag and restart gateway
sed -i 's/^XNCH_MEMORY_EMBEDDED=false/XNCH_MEMORY_EMBEDDED=true/' ~/.xnch/xnch.env
sudo systemctl restart xnch
# Gateway re-owns Kuzu file; memory-service can remain running (it owns Kuzu
# only in remote mode; stop it first if both would contend).
```

**Embedded → Remote (re-apply):**
```bash
sed -i 's/^XNCH_MEMORY_EMBEDDED=true/XNCH_MEMORY_EMBEDDED=false/' ~/.xnch/xnch.env
sudo systemctl restart xnch
```

The `XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:8003` and `XNCH_MEMORY_TOKEN`
must already be set in `~/.xnch/xnch.env`. This flip is the same procedure
documented in [memory-service-deploy.md](memory-service-deploy.md#rollback-instant)
and has been rehearsed.

## Data safety

Before either path: back up Postgres volumes (`pgdata`, `langfuse-pgdata`) and
`~/.xnch/` (keys, audit ledger, SQLite stores, graph.kuzu).
