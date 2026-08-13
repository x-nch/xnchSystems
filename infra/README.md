# XNCH / Nexi Deployment

Two physical nodes running the xnch/nexi stack **without k3s** — docker compose + systemd.
This replaced the k3s cluster (see `no-k3s/MIGRATION.md` for the migration and rollback plan).

| Node | Hostname | IP | Hardware | Role |
|------|----------|-----|----------|------|
| Node A | `gate7` (i7-node) | `192.168.50.1` | Intel i7 + GTX 1650 | Control plane, memory layer, observability |
| Node B | `xnch-core` (i9-node) | `192.168.50.2` | Intel i9 + RTX 3090 | Inference (vLLM Ornith) + Nexi engine |

Node B is WoL-wakeable from Node A (`wakecore`). It sleeps when idle.

---

## Node A — Control Plane (gate7, 192.168.50.1)

Docker compose stack (`infra/no-k3s/node-a/docker-compose.yml`):

| Service | Port | Purpose |
|---|---|---|
| litellm | 4000 | Model routing gateway (→ vLLM Ornith on Node B) |
| langfuse | 3000 | LLM observability and tracing |
| langfuse-postgres | 5433 | Langfuse's own PostgreSQL instance |
| postgres-pgvector | 5432 | Episodic store, relationship store, quarantine store |
| redis | 6379 | KV cache, sensory buffer (L0), working memory (L1), session dedup |
| searxng | 8888 (loopback only) | Web search for agents |

Systemd units (`infra/no-k3s/node-a/systemd/`):

| Unit | Port | Purpose |
|---|---|---|
| `xnch.service` | 8001 | Control plane API (REST, auth, policy, memory) |
| `consolidation.timer` | — | Daily memory consolidation job |

## Node B — Inference (xnch-core, 192.168.50.2)

No Docker on Node B — bare venv + systemd (`infra/no-k3s/node-b/systemd/`):

| Unit | Port | Purpose |
|---|---|---|
| `nvidia-ready.service` | — | Waits for the NVIDIA driver after boot |
| `vllm-ornith.service` | 8082 | vLLM serving `ornith-gptq-pro` (OpenAI-compatible API) |
| `nexi.service` | 8000 | Nexi decision engine (context, options, scoring, dispatch) |

Node B depends on Node A (redis, postgres, xnch, litellm) via `~/.xnch/nexi.env`.

---

## Quickstart

### Prerequisites

- Docker running on Node A; systemd on both nodes.
- Env files on Node A (`~/.xnch/xnch.env`) and Node B (`~/.xnch/nexi.env`).
  Templates in `infra/no-k3s/shared/.env.example`. Also: vLLM model dir
  (`~/models/ornith-gptq-pro`), vLLM venv (`~/venvs/vllm-ornith`), and the
  `xnch`/`nexi` venvs must exist on their nodes.
- NVIDIA driver on Node B (run once if missing:
  `sudo infra/no-k3s/node-b/setup-gpu-driver.sh && sudo reboot`).

### Spin up Node A (from Node A)

```bash
cd ~/xnchSystems/infra/no-k3s/node-a
./start-node-a.sh --wake-node-b --wait-node-b
```

Options: `--install` (copy systemd units), `--skip-docker`, `--wake-node-b`
(send WoL and wait for ping), `--wait-node-b` (wait for vLLM :8082),
`--no-litellm-restart`.

### Spin up Node B (from Node B)

```bash
ssh x-nch@192.168.50.2
cd ~/xnchSystems/infra/no-k3s/node-b
./start-node-b.sh --install
```

Options: `--install`, `--skip-vllm`, `--no-wait-node-a`.

### Wake Node B remotely (from Node A)

```bash
./infra/no-k3s/node-a/wake-node-b.sh   # WoL, then waits up to 180s for ping
```

---

## Verify

### Health

```bash
curl -sf http://localhost:8001/health           # xnch (Node A)
curl -sf http://localhost:4000/health/liveliness # litellm (Node A)
curl -sf http://192.168.50.2:8082/health         # vLLM (Node B)
curl -sf http://192.168.50.2:8000/health         # nexi (Node B)
```

### End-to-end smoke test (from Node A)

```bash
cd ~/xnchSystems/infra/no-k3s
./e2e-test.sh
```

Requires an `operator` actor and valid `XNCH_AUTH_SECRET`. Checks health of
all four services, litellm model registration (`ornith`), session init through
the nexi pipeline, and both chat endpoints.

---

## Configuration

- `infra/no-k3s/node-a/docker-compose.yml` — Node A container stack.
- `infra/no-k3s/node-a/.env` — docker compose secrets (POSTGRES, LANGFUSE, LITELLM keys).
- `infra/no-k3s/node-a/litellm-config/` — litellm config; routing to Node B in
  `infra/no-k3s/shared/litellm-routing.yaml` (`api_base: http://192.168.50.2:8082/v1`).
- `~/.xnch/xnch.env` — xnch service env (Node A).
- `~/.xnch/nexi.env` — nexi service env; cross-node URLs (Node A IPs) (Node B).
- `infra/no-k3s/shared/` — env template, litellm routing, MCP server, memory-routing,
  web-search, exec-policy, fs-policy examples.
- `infra/no-k3s/MIGRATION.md` — k3s → direct management migration + rollback.

## Deferred Components

perception service (`:8002`), vault-indexer, and nexiUI are not yet implemented;
the systemd units exist but are not enabled.
