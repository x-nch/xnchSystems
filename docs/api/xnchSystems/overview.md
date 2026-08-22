# Overview

## System topology

Two-node home cluster on the `192.168.1.0/24` LAN, with a private
`192.168.50.0/24` node link between the two servers. A MacBook is a third,
client-only participant.

```
┌────────────────────────── MacBook (192.168.1.11) ──────────────────────────┐
│  cli (python -m cli / xnch-cli)     xnch-mcp stdio client                 │
│  XNCH_BASE_URL=http://192.168.1.10:8001                                    │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │ home LAN only
┌───────────────────────────────────────▼────────────────────────────────────┐
│ gate7 / node-a  (192.168.1.10 = 192.168.50.1)  Control plane               │
│  xnch         :8001   (uvicorn xnch.main:app)                              │
│  LiteLLM      :4000   (Docker, model proxy → node-b vLLMs)                 │
│  Langfuse     :3000   (Docker, observability)                              │
│  Postgres     :5432   (Docker, pgvector)                                   │
│  Redis        :6379   (Docker, shared state)                               │
│  SearXNG      :8888   (Docker, web search, loopback)                       │
│  Tailscale funnel: 443 → :8001 (public HTTPS)                              │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │ node link 192.168.50.0/24
┌───────────────────────────────────────▼────────────────────────────────────┐
│ xnch-core / node-b  (192.168.1.9 = 192.168.50.2)  Product plane            │
│  nexi            :8000   (uvicorn nexi.main:app, decision/policy pipeline) │
│  vLLM ornith     :8082   (Ornith-1.0-35B, GPTQ-Pro, agentic coding)        │
│  vLLM qwen-vl    :8083   (Qwen2.5-VL-7B AWQ, image/video)                  │
│  fs-read-agent   :8003   (read-only filesystem MCP backend)                │
│  exec-agent      :8004   (governed command execution MCP backend)          │
│  media-gateway   :8090   (media jobs → ComfyUI / qwen-vl)                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Service roles

| Service | Repo dir | Role |
|---------|----------|------|
| **xnch** | `xnch/` | Control plane. Session pipeline, memory, policy, verdicts, execution stubs, governance, auth, MCP bridge, Nexi gateway routes. Owns the `/mcp/*` and `/nexi/*` HTTP surfaces on gate7. |
| **nexi** | `nexi/` | Product/execution plane. Runs the intent→decision→dispatch pipeline on node-b and calls back into xnch for memory/policy/execution via its `XnchClient` adapter. |
| **LiteLLM** | infra (Docker) | Model gateway on gate7 :4000; routes `ornith` / `qwen-vl` / `qwen2.5-vl-7b` to the node-b vLLM instances. |
| **fs-read-agent** | `fs_read_agent/` | Read-only filesystem HTTP agent on node-b :8003, backed by `xnch_mcp.fs` with a policy allowlist. |
| **exec-agent** | `exec_agent/` | Governed command execution agent on node-b :8004, backed by `xnch_mcp.exec` allowlist/deny policy. |
| **media-gateway** | `media-gateway/` | Media job queue on node-b :8090; dispatches to ComfyUI and qwen-vl understanding. |

## Call paths

- **Mac → xnch (gate7)**: Mac never touches `192.168.50.0/24`; it only calls
  `http://192.168.1.10:8001`. All product-plane traffic is proxied by xnch.
- **xnch → nexi**: `XNCH_NEXI_BASE_URL` (default `http://localhost:8000`).
  On gate7 this must be overridden to `http://192.168.50.2:8000` for cross-node
  calls (see systemd unit). Used by session/verdict flows.
- **nexi → xnch**: `NEXI_XNCH_BASE_URL` (default `http://localhost:8001`).
  On node-b this is overridden to `http://192.168.50.1:8001`. `XnchClient`
  posts `/memory/read`, `/policy/check`, and related endpoints.
- **xnch → LiteLLM**: `/nexi/chat*` and `/v1/chat/completions` call
  `LITELLM_BASE_URL` / `settings.litellm_proxy_url` (default
  `http://litellm:4000`) with `LITELLM_API_KEY` or `LITELLM_MASTER_KEY`.
- **LiteLLM → vLLM**: config maps `ornith` → `http://192.168.50.2:8082/v1`,
  `qwen-vl` / `qwen2.5-vl-7b` → `http://192.168.50.2:8083/v1` (key
  `xnch-vllm-key`).
- **nexi → vLLM directly**: primary `http://192.168.50.2:8083/v1`, model
  `qwen2.5-vl-7b` (for image/video understanding tasks).
- **nexi → xnch execution**: `NEXI_EXECUTION_RUNNER_URL` (default
  `http://192.168.50.1:8001/execution`) — dispatch target for executed actions.

## Shared state

- **Redis**: xnch uses TCP (`redis://localhost:6379/0`); nexi uses the Unix
  socket (`unix:///tmp/xnch-redis.sock`) on node-b.
- **Postgres (pgvector)**: episodic memory / graph store, single Docker instance
  on gate7 :5432.
- **Langfuse**: tracing for both planes, gate7 :3000.

## Environment variables

Prefixes: `XNCH_*` for the control plane, `NEXI_*` for the product plane,
`MEDIA_GATEWAY_*` for media-gateway, `LITELLM_*` for gateway/auth keys.

### CLI (`cli/config.py`, `xnch_mcp` stdio server)

| Var | Default | Purpose |
|-----|---------|---------|
| `XNCH_BASE_URL` | `http://localhost:8001` (`127.0.0.1:8001` in stdio) | Control plane base URL |
| `NEXI_BASE_URL` | `http://localhost:8000` | Nexi base URL (health checks) |
| `XNCH_AUTH_SECRET` | — | HS256 secret for minting dev JWTs |
| `XNCH_AUTH_TOKEN` | — | Pre-signed bearer token; passed straight through as `Authorization` |
| `XNCH_ACTOR` | `operator` | Default actor identity |
| `XNCH_VOICE_INPUT_DEVICE` | — | Mic device for push-to-talk |
| `XNCH_VOICE_MUTE` | `0` | Mute state for voice session |
| `XNCH_VOICE_SAMPLE_RATE` | `16000` | Audio sample rate |

### xnch control plane (`xnch/config.py`, prefix `XNCH_`)

| Var | Default | Purpose |
|-----|---------|---------|
| `XNCH_AUTH_SECRET` | — | HS256 dev-token secret |
| `XNCH_TOKEN_TTL_MS` | — | Execution token TTL |
| `XNCH_SESSION_TTL_S` | — | Session TTL |
| `XNCH_RATE_LIMIT_PER_MINUTE` | — | Rate limit on session/init |
| `XNCH_NEXI_BASE_URL` | `http://localhost:8000` | Nexi URL for gateway calls |
| `XNCH_REDIS_URL` | — | Redis TCP URL |
| `XNCH_POSTGRES_URL` | — | pgvector DSN |
| `XNCH_LITELLM_PROXY_URL` | `http://litellm:4000` | LiteLLM base for chat/completions |
| `XNCH_AM_PREFETCH_ENABLED` | — | Proactivity prefetch toggle |
| `XNCH_FS_AGENT_BIND` / `XNCH_FS_AGENT_PORT` | `127.0.0.1` / `8003` | fs-read-agent bind |
| `XNCH_EXEC_AGENT_BIND` / `XNCH_EXEC_AGENT_PORT` | `127.0.0.1` / `8004` | exec-agent bind |
| `XNCH_FS_POLICY_PATH`, `XNCH_EXEC_POLICY_PATH` | `infra/no-k3s/shared/fs-policy.yaml`, `.../exec-policy.yaml` | policy files |
| `XNCH_FS_AGENT_TOKEN`, `XNCH_EXEC_AGENT_TOKEN` | — | internal `X-Internal-Token` for sidecar agents |
| `XNCH_MCP_MAX_TOOL_ROUNDS`, `XNCH_MCP_MAX_TOOL_ROUNDS_WITH_BRIDGE` | — | tool-loop round caps |

### nexi product plane (`nexi/config.py`, prefix `NEXI_`)

| Var | Default | Purpose |
|-----|---------|---------|
| `NEXI_XNCH_BASE_URL` | `http://localhost:8001` | xnch URL for memory/policy calls |
| `NEXI_VLLM_PRIMARY_URL` | `http://192.168.50.2:8083/v1` | vLLM for vision understanding |
| `NEXI_VLLM_MODEL_ID` | `qwen2.5-vl-7b` | Vision model id |
| `NEXI_LITELLM_PROXY_URL` | `http://localhost:4000/v1` | LiteLLM for text routing |
| `NEXI_EXECUTION_RUNNER_URL` | `http://192.168.50.1:8001/execution` | Dispatch target |
| `NEXI_REDIS_URL` | `unix:///tmp/xnch-redis.sock` | Shared Redis socket |
| `NEXI_AUDIT_EVENTS_PATH` | — | Audit event persistence |

### Gateway keys

| Var | Purpose |
|-----|---------|
| `LITELLM_BASE_URL` | LiteLLM base for `/nexi/chat*` and `/v1/chat/completions` |
| `LITELLM_API_KEY` / `LITELLM_MASTER_KEY` | Bearer key sent to LiteLLM |

### media-gateway (`MEDIA_GATEWAY_*`)

`MEDIA_GATEWAY_TOKEN` (required for all `/media/*` routes, fail-closed),
`MEDIA_GATEWAY_BIND` (private interface), `MEDIA_GATEWAY_PORT` (`8090`),
`MEDIA_GATEWAY_INBOX_DIR` / `MEDIA_GATEWAY_OUTBOX_DIR`, `MEDIA_GATEWAY_MAX_UPLOAD_MB`
(`200`), `MEDIA_GATEWAY_ALLOWED_EXTENSIONS` (png, jpg, jpeg, webp, mp4, mov),
`MEDIA_GATEWAY_COMFY_URL` / `_INPUT_DIR` / `_OUTPUT_DIR` / `_WORKFLOWS_DIR`,
`MEDIA_GATEWAY_LITELLM_URL` (default `http://127.0.0.1:8083/v1`),
`MEDIA_GATEWAY_QWEN_MODEL` (`qwen-vl`), plus `LANGFUSE_PUBLIC_KEY` /
`LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`.

## Deployment units (systemd)

**gate7 / node-a**
- `xnch.service` — uvicorn `xnch.main:app` on :8001 (PYTHONPATH includes `xnch`).
- `tailscale-funnel-xnch.service` — public HTTPS 443 → :8001.
- `consolidation.service` / `consolidation.timer` — 02:00 UTC daily memory
  consolidation.
- Docker: `litellm` :4000, `langfuse` :3000, `postgres-pgvector` :5432,
  `redis` :6379, `searxng` :8888 (loopback).

**xnch-core / node-b**
- `nexi.service` — :8000.
- `vllm-ornith.service` — :8082 (Conflicts with qwen-vl; both are GPU-heavy).
- `qwen-vl.service` — :8083.
- `fs-read-agent.service` — `python -m fs_read_agent`, :8003.
- `exec-agent.service` — `python -m exec_agent`, :8004.
- `media-gateway.service` — `python -m media_gateway.main`, :8090
  (Conflicts with vllm-ornith).

## Conventions

- All data models are Pydantic; serialization is `model_dump(mode="json")`.
- HTTP responses use `resp.raise_for_status()` after status checks.
- Environment is Pydantic `BaseSettings`; paths are `Path` and expanded via
  `.expanduser()`.
