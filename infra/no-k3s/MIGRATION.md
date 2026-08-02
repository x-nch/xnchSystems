# Migration: k3s → Direct Service Management

## Overview

Migrate xnchSystems from a k3s cluster to direct service management across two physical nodes.

| Node | Hardware | Role |
|------|----------|------|
| Node A (i7-node) | Intel i7 + GTX 1650 | Control plane, memory layer, observability |
| Node B (i9-node) | Intel i9 + RTX 3090 | Inference (vLLM Ornith) + Nexi engine |

## Pre-Migration Checklist

- [ ] Verify static IPs: Node A = `192.168.50.1`, Node B = `192.168.50.2`
- [ ] Verify Docker is installed and running on both nodes
- [ ] Verify systemd is available on both nodes
- [ ] Create `.env` files from `shared/.env.example` on both nodes with actual values
- [ ] Backup all k8s manifests: `cp -r deploy/k8s deploy/k8s.backup.$(date +%Y%m%d)`
- [ ] Backup PostgreSQL data from existing postgres-pgvector PVC
- [ ] Backup Langfuse data if applicable
- [ ] Confirm mem0 is already decommissioned (confirmed in addendum)
- [ ] Confirm zep is already decommissioned (confirmed in addendum)
- [ ] Confirm llama.cpp is no longer needed (confirmed in addendum)

## Required Code Changes

Before deploying, update these config files in the codebase:

### nexi/nexi/config.py (Node B — nexi service)

| Setting | Old (k8s) | New (no-k3s) |
|---------|-----------|-------------|
| `vllm_primary_url` | `http://localhost:8000/v1` | `http://localhost:8082/v1` |
| `vllm_health_url` | `http://vllm-gemma4:8000/health` | `http://localhost:8082/health` |
| `litellm_proxy_url` | `http://localhost:4000/v1` | Override via `NEXI_LITELLM_PROXY_URL` env var → `http://NODE_A_IP:4000/v1` |
| `redis_url` | `unix:///tmp/xnch-redis.sock` | Override via `NEXI_REDIS_URL` env var → `redis://NODE_A_IP:6379/0` |
| `xnch_base_url` | `http://localhost:8001` | Override via `NEXI_XNCH_BASE_URL` env var → `http://NODE_A_IP:8001` |
| `postgres_url` | (not set, uses env) | Override via `NEXI_POSTGRES_URL` env var → `postgresql://xnch:PASSWORD@NODE_A_IP:5432/xnch` |

### xnch/xnch/config.py (Node A — xnch service)

| Setting | Old (k8s) | New (no-k3s) |
|---------|-----------|-------------|
| `litellm_proxy_url` | `http://litellm:4000` | `http://localhost:4000` |

## Phase 1 — Deploy Node A Services

### 1.1 Copy configs to Node A

```bash
scp -r infra/no-k3s/node-a/ x-nch@NODE_A_IP:~/xnchSystems/infra/no-k3s/
scp infra/no-k3s/shared/.env.example x-nch@NODE_A_IP:~/.xnch/.env
scp infra/no-k3s/shared/litellm-routing.yaml x-nch@NODE_A_IP:~/xnchSystems/xnch/litellm_config.yaml
```

### 1.2 Edit environment files

On Node A, edit `~/.xnch/xnch.env`:
```bash
POSTGRES_PASSWORD=<actual-password>
LANGFUSE_POSTGRES_PASSWORD=<actual-password>
LANGFUSE_NEXTAUTH_SECRET=<actual-secret>
LANGFUSE_SALT=<actual-salt>
LITELLM_MASTER_KEY=<actual-key>
XNCH_AUTH_SECRET=<actual-secret>
```

### 1.3 Start Docker Compose services on Node A

```bash
cd ~/xnchSystems/infra/no-k3s/node-a
docker compose up -d
```

Verify services are healthy:
```bash
docker compose ps
curl -sf http://localhost:4000/health   # litellm
curl -sf http://localhost:3000/api/auth/verify  # langfuse
curl -sf http://localhost:6379/ping      # redis
curl -sf http://localhost:5432           # postgres-pgvector
```

### 1.4 Enable and start systemd services on Node A

```bash
sudo cp infra/no-k3s/node-a/systemd/*.service /etc/systemd/system/
sudo cp infra/no-k3s/node-a/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable xnch.service perception.service consolidation.timer
sudo systemctl start xnch.service perception.service
sudo systemctl start consolidation.timer
```

### 1.5 Update LiteLLM routing config

Replace `NODE_B_IP` in `litellm-routing.yaml` with the actual Node B IP (`192.168.50.2`).

### 1.6 Validate Node A

- [ ] xnch responds on `http://localhost:8001`
- [ ] litellm responds on `http://localhost:4000`
- [ ] langfuse responds on `http://localhost:3000`
- [ ] redis responds on `localhost:6379`
- [ ] postgres-pgvector responds on `localhost:5432`
- [ ] langfuse-postgres responds on `localhost:5433`
- [ ] perception service responds on `localhost:8002`
- [ ] consolidation timer is active (`systemctl list-timers`)

## Phase 2 — Deploy Node B Services

### 2.1 Copy configs to Node B

```bash
scp -r infra/no-k3s/node-b/ x-nch@NODE_B_IP:~/xnchSystems/infra/no-k3s/
scp infra/no-k3s/shared/.env.example x-nch@NODE_B_IP:~/.xnch/.env
```

### 2.2 Edit environment files on Node B

On Node B, edit `~/.xnch/nexi.env`:
```bash
POSTGRES_PASSWORD=<actual-password>
NEXI_LITELLM_PROXY_URL=http://NODE_A_IP:4000/v1
NEXI_XNCH_BASE_URL=http://NODE_A_IP:8001
NEXI_REDIS_URL=redis://NODE_A_IP:6379/0
NEXI_POSTGRES_URL=postgresql://xnch:POSTGRES_PASSWORD@NODE_A_IP:5432/xnch
```

### 2.3 Enable and start systemd services on Node B

```bash
sudo cp infra/no-k3s/node-b/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vllm-ornith.service nexi.service
sudo systemctl start vllm-ornith.service nexi.service
```

### 2.4 Validate Node B

- [ ] vLLM Ornith responds on `http://localhost:8082/v1` (OpenAI-compatible)
- [ ] vLLM Ornith health check: `curl -sf http://localhost:8082/health`
- [ ] nexi responds on `http://localhost:8000`
- [ ] nexi can reach litellm on Node A: `curl -sf http://NODE_A_IP:4000/health`
- [ ] nexi can reach xnch on Node A: `curl -sf http://NODE_A_IP:8001`
- [ ] nexi can reach redis on Node A: `redis-cli -h NODE_A_IP ping`
- [ ] nexi can reach postgres on Node A: `pg_isready -h NODE_A_IP -U xnch`

## Phase 3 — Cross-Node Validation

### 3.1 Test full pipeline

From Node A:
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3-xml", "messages": [{"role": "user", "content": "hello"}]}'
```

This should route through litellm → vLLM Ornith on Node B → response back through litellm.

### 3.2 Test nexi pipeline

```bash
curl -X POST http://NODE_A_IP:8001/v1/nexi/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

### 3.3 Test Langfuse tracing

Verify traces appear in Langfuse UI at `http://NODE_A_IP:3000`.

## Rollback Plan

If anything goes wrong, revert to the k3s cluster:

### 3.1 Stop Node B services

```bash
sudo systemctl stop nexi.service vllm-ornith.service
sudo systemctl disable nexi.service vllm-ornith.service
```

### 3.2 Stop Node A services

```bash
cd ~/xnchSystems/infra/no-k3s/node-a
docker compose down
sudo systemctl stop xnch.service perception.service consolidation.timer
sudo systemctl disable xnch.service perception.service consolidation.timer
```

### 3.3 Restore k3s

```bash
# Re-enable k3s if stopped
sudo systemctl start k3s

# Re-apply k8s manifests
kubectl apply -f deploy/k8s/

# Verify k8s pods are running
kubectl get pods -n xnch-system
```

### 3.4 Restore nexi config.py defaults

Revert `vllm_primary_url` to `http://localhost:8000/v1` and `litellm_proxy_url` to `http://litellm:4000` if needed.

## Key Changes from k3s Setup

| Aspect | k3s (old) | Direct (new) |
|--------|-----------|-------------|
| Networking | Flannel overlay (10.42.x.x) | Static IPs on 192.168.50.0/24 |
| DNS | CoreDNS / k8s service names | Direct IP or localhost |
| Container runtime | k3s containerd | Docker on host |
| Service management | k8s Deployments/CronJobs | systemd + docker compose |
| Postgres | Single pgvector instance | Two instances (xnch + langfuse) |
| vLLM | llama.cpp on 8080 → Endpoints | vLLM Ornith on 8082 |
| mem0 | Deployed in k8s | Decommissioned |
| zep | Deployed in k8s | Decommissioned |
| llama.cpp | Bare metal on i9 | Removed |
| nexiUI | Not deployed | Planned for Node A |

## File Manifest

```
infra/no-k3s/
├── MIGRATION.md
├── node-a/
│   ├── docker-compose.yml
│   └── systemd/
│       ├── xnch.service
│       ├── perception.service
│       ├── consolidation.service
│       ├── consolidation.timer
│       └── vault-indexer.service
├── node-b/
│   └── systemd/
│       ├── vllm-ornith.service
│       └── nexi.service
└── shared/
    ├── litellm-routing.yaml
    └── .env.example
```