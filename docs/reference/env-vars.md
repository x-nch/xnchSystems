# Environment Variable Reference

Generated from `xnch/config.py`, `nexi/config.py`,
`xnch-train/xnch_train/config.py`, gateway/chat relay code, and `web/` —
**exhaustive**, not sampled. Pydantic-settings maps each snake_case field to
`<PREFIX>_<FIELD_UPPER>`; `.env` files supported (`~/.xnch/*.env` on nodes).
Secrets below are placeholders; never commit real values.

## XNCH_* — control plane (`xnch/config.py`)

### Core

| Variable | Default | Description |
|---|---|---|
| `XNCH_BASE_DIR` | `~/.xnch` | data root: keys/, audit/, governance/, policies/, weights/, data/ |
| `XNCH_REDIS_URL` | `redis://localhost:6379/0` | L0/L1/KV/dedup/rate-limit |
| `XNCH_AUTH_SECRET` | `dev-secret-change-in-production` | HS256 bearer secret — set real value in prod |
| `XNCH_TOKEN_TTL_MS` | `30000` | RS256 execution-token TTL |
| `XNCH_SESSION_TTL_S` | `120` | session TTL |
| `XNCH_RATE_LIMIT_PER_MINUTE` | `10` | per-actor request cap |
| `XNCH_NEXI_BASE_URL` | `http://localhost:8000` | nexi callback URL |
| `XNCH_SELF_BASE_URL` | `http://localhost:8001` | used by background jobs POSTing to own API |
| `XNCH_POSTGRES_URL` | *(dsn)* NOTE: source default embeds credentials — supply real DSN via env only | pgvector stores |

### Learning & recall

| Variable | Default | Description |
|---|---|---|
| `XNCH_PATTERN_MIN_OBSERVATIONS` | `10` | episodes before pattern extraction |
| `XNCH_SCORE_ADAPTER_ACCURACY_THRESHOLD` | `0.6` | accuracy floor for weight adaptation |
| `XNCH_MEMORY_RECALL_MIN_SCORE` | `0.35` | similarity floor for chat recall |

### Observability & LLM

| Variable | Default | Description |
|---|---|---|
| `XNCH_LANGFUSE_PUBLIC_KEY` / `_SECRET_KEY` | `""` (disabled) | Langfuse tracing creds |
| `XNCH_LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse host |
| `XNCH_LITELLM_PROXY_URL` | `http://litellm:4000` | LiteLLM proxy base |
| `XNCH_LLM_STATUS_URL` | `http://192.168.50.2:8082/health` | vLLM health probe |
| `XNCH_LLM_MODEL_ID` | `ornith-1.0-35b` | expected served model name |
| `XNCH_LLM_PROBE_TIMEOUT_S` | `3.0` | probe timeout |
| `XNCH_GRAPH_EXTRACTOR_MODEL` | `ornith` | consolidation extractor model (`llama_cpp/<file>` opts into local backend) |
| `XNCH_GRAPH_EXTRACTOR_PROVIDER_HINT` | `""` | provider hint for extraction |

### Perception

| Variable | Default | Description |
|---|---|---|
| `XNCH_VAULT_DIR` | `~/.xnch/vault` | file-watch vault root |
| `XNCH_PERCEPTION_REDIS_DB` | `0` | perception signal Redis DB |
| `XNCH_ATTENTION_SILENCE_THRESHOLD_S` | `1.5` | voice silence trigger |
| `XNCH_ATTENTION_SCREEN_DIFF_THRESHOLD` | `0.15` | screen-change fraction |
| `XNCH_ATTENTION_IDLE_TIMEOUT_S` | `600` | idle before consolidation |

### Filesystem agent (fs)

| Variable | Default | Description |
|---|---|---|
| `XNCH_FS_POLICY_PATH` | `~/.xnch/fs-policy.yaml` | read-only FS policy |
| `XNCH_FS_LOCAL_HOST` | `node-a` | which node this process serves reads for |
| `XNCH_FS_AGENT_NODE_B_URL` | `http://192.168.50.2:8003` | Node B fs-read-agent |
| `XNCH_FS_AGENT_TOKEN` | `""` | agent bearer token |
| `XNCH_FS_MAX_READ_BYTES` | `2097152` | 2 MiB read cap |
| `XNCH_FS_MAX_LIST_ENTRIES` | `1000` | listing cap |
| `XNCH_FS_MAX_GLOB_RESULTS` | `200` | glob cap |

### Exec agent

| Variable | Default | Description |
|---|---|---|
| `XNCH_EXEC_POLICY_PATH` | `~/.xnch/exec-policy.yaml` | governed command policy |
| `XNCH_EXEC_LOCAL_HOST` | `node-a` | which node this process runs commands on |
| `XNCH_EXEC_AGENT_NODE_B_URL` | `http://192.168.50.2:8004` | Node B exec-agent |
| `XNCH_EXEC_AGENT_TOKEN` | `""` | agent bearer token |

### MCP bridge & tools

| Variable | Default | Description |
|---|---|---|
| `XNCH_MCP_BRIDGE_ENABLED` | `true` | spawn federated MCP servers at startup |
| `XNCH_MCP_SERVERS_PATH` | `~/.xnch/mcp-servers.yaml` | server declarations |
| `XNCH_MCP_MAX_TOOL_ROUNDS` | `3` | chat tool-loop cap (explicit override wins) |
| `XNCH_MCP_MAX_TOOL_ROUNDS_WITH_BRIDGE` | `5` | cap while bridge servers are connected |

### Web search & memory routing

| Variable | Default | Description |
|---|---|---|
| `XNCH_WEB_SEARCH_POLICY_PATH` | `~/.xnch/web-search.yaml` | search policy |
| `XNCH_SEARXNG_URL` | `http://127.0.0.1:8888` | SearXNG endpoint |
| `XNCH_MEMORY_ROUTING_POLICY_PATH` | `~/.xnch/memory-routing.yaml` | episodic vs agentmemory routing |
| `XNCH_AM_PREFETCH_ENABLED` | `false` | prefetch curated memories |

### HITL & workflows

| Variable | Default | Description |
|---|---|---|
| `XNCH_LANGGRAPH_PIPELINE` | `false` | enable LangGraph pipeline + interrupts |
| `XNCH_HITL_EXECUTION_MODE` | `always` | when to interrupt |
| `XNCH_HITL_RISK_THRESHOLD` | `0.5` | risk gate threshold |
| `XNCH_GATEWAY_SECRET` | `""` NOTE empty = Hybrid-B write-gate OPEN | HMAC secret shared with muse proxy |
| `XNCH_WORKFLOW_EXECUTOR_ENABLED` | `false` | true = approve leaves steps APPROVED for nexi claim |
| `XNCH_WORKFLOW_STEP_CLAIM_LEASE_S` | `120` | claim lease TTL |

### Voice

| Variable | Default | Description |
|---|---|---|
| `XNCH_VOICE_ENABLED` | `true` | STT/TTS routes on/off |
| `XNCH_VOICE_STT_MODEL` | `base` | whisper model size |
| `XNCH_VOICE_STT_DEVICE` | `cpu` | STT device |
| `XNCH_VOICE_STT_COMPUTE_TYPE` | `int8` | CT2 compute type |
| `XNCH_VOICE_STT_LANGUAGE` | `en` | STT language |
| `XNCH_VOICE_TTS_ENGINE` | `piper` | TTS engine |
| `XNCH_VOICE_TTS_VOICE_PATH` | `~/.xnch/voice/en_US-lessac-medium.onnx` | piper voice model |
| `XNCH_VOICE_TTS_CONFIG_PATH` | `~/.xnch/voice/en_US-lessac-medium.onnx.json` | piper config |
| `XNCH_VOICE_MAX_AUDIO_DURATION_S` | `60.0` | upload cap |
| `XNCH_VOICE_MAX_AUDIO_BYTES` | `10485760` | 10 MiB upload cap |
| `XNCH_VOICE_MAX_TTS_CHARS` | `2000` | TTS input cap |
| `XNCH_VOICE_MODELS_DIR` | `~/.xnch/voice/models` | whisper download dir |

## NEXI_* — decision engine (`nexi/config.py`)

### Control-plane & models

| Variable | Default | Description |
|---|---|---|
| `NEXI_XNCH_BASE_URL` | `http://localhost:8001` | xnch API base (Node B uses `http://192.168.50.1:8001`) |
| `NEXI_XNCH_PUBLIC_KEY_PATH` | `~/.xnch/keys/public.pem` | RS256 public key for execution-token verification |
| `NEXI_VLLM_PRIMARY_URL` | `http://192.168.50.2:8082/v1` | primary vLLM (Ornith) endpoint |
| `NEXI_VLLM_PRIMARY_TIMEOUT_S` | `30.0` | primary timeout |
| `NEXI_VLLM_SECONDARY_URL` / `_TIMEOUT_S` | `""` / `45.0` | optional fallback vLLM |
| `NEXI_MODEL_ID` | `ornith-1.0-35b` | served model id |
| `NEXI_OPTIONS_COUNT` | `5` | plan options per intent |

### LiteLLM & classification

| Variable | Default | Description |
|---|---|---|
| `NEXI_LITELLM_PROXY_URL` | `http://localhost:4000/v1` | LiteLLM chat endpoint (Node B: `http://192.168.50.1:4000/v1`) |
| `NEXI_LITELLM_PROXY_TIMEOUT_S` | `60.0` | proxy timeout |
| `NEXI_LITELLM_API_KEY` | `""` | proxy key if required |
| `NEXI_INTENT_CLASSIFIER_MODEL` | `ornith` | intent classifier |
| `NEXI_REFLECTION_MODEL` / `_ENABLED` | `ornith` / `true` | post-decision reflection call |

### Sessions, redis, execution

| Variable | Default | Description |
|---|---|---|
| `NEXI_SESSION_TTL_S` / `NEXI_CLARIFICATION_TTL_S` | `120` / `120` | session TTLs |
| `NEXI_EXECUTION_TOKEN_TTL_MS` | `30000` | expected execution-token validity |
| `NEXI_REDIS_URL` | `unix:///tmp/xnch-redis.sock` | shared Redis (Node B: `redis://192.168.50.1:6379/0`) |
| `NEXI_EXECUTION_RUNNER_URL` | `http://192.168.50.1:8001/execution` | dispatch target |
| `NEXI_VLLM_HEALTH_URL` | `http://192.168.50.2:8082/health` | proactivity health check |
| `NEXI_AUDIT_EVENTS_PATH` | `~/.xnch/audit/events.jsonl` | local audit mirror |

### Capabilities auto-refresh

| Variable | Default | Description |
|---|---|---|
| `NEXI_CAPABILITIES_GENERATED_PATH` | `~/.xnch/nexi-capabilities.generated.yaml` | generated capability doc |
| `NEXI_MCP_SERVERS_PATH` | `~/.xnch/mcp-servers.yaml` | bridge server list |
| `NEXI_INFRA_MANIFESTS_PATH` | `<pkg>/infra/no-k3s` | infra manifests root |
| `NEXI_EXEC_POLICY_PATH` / `NEXI_FS_POLICY_PATH` | `~/.xnch/exec-policy.yaml` / `~/.xnch/fs-policy.yaml` | policy mirrors for capability docs |
| `NEXI_CAPABILITY_REFRESH_INTERVAL_S` | `300` | refresh cadence |
| `NEXI_PROBE_INTERVAL_S` / `NEXI_PROBE_TIMEOUT_S` | `60` / `2.0` | infra probes |
| `NEXI_XNCH_TOOLS_ENDPOINT` | `/nexi/tools` | tools endpoint path |
| `NEXI_CAPABILITY_AUTO_REFRESH` | `true` | toggle background refresh |

### Goal driver & workflow executor

| Variable | Default | Description |
|---|---|---|
| `NEXI_GOAL_DRIVER_ENABLED` | `false` | autonomous goal loop on/off |
| `NEXI_GOAL_POLL_INTERVAL_S` | `5` | goal claim poll |
| `NEXI_GOAL_DEFAULT_MAX_STEPS` | `10` | steps per goal |
| `NEXI_GOAL_DEFAULT_FAILURE_THRESHOLD` | `3` | failures before goal fails |
| `NEXI_GOAL_MAX_CONSECUTIVE_STEP_ERRORS` | `3` | consecutive-error circuit breaker |
| `NEXI_WORKFLOW_EXECUTOR_ENABLED` | `false` | claims APPROVED workflow steps from xnch |
| `NEXI_WORKFLOW_POLL_INTERVAL_S` | `5` | executor claim poll |

## XTRAIN_* — training pipeline (`xnch-train/xnch_train/config.py`)

| Variable | Default | Description |
|---|---|---|
| `XTRAIN_DATASET_DIR` | `./datasets` | dataset home (Node A filesystem) |
| `XTRAIN_POSTGRES_URL` | `postgresql://localhost:5432/xnch` | outcome/correction extracts |
| `XTRAIN_LANGFUSE_HOST` / `_PUBLIC_KEY` / `_SECRET_KEY` | `""` | trace extraction creds |
| `XTRAIN_PSEUDONYMIZE_SECRET` | **required** — startup fails when empty | HMAC key for entity pseudonymization |
| `XTRAIN_GATE_EPSILON` | `0.02` | promotion-gate metric tolerance (dry-run) |
| `XTRAIN_SERVING_REGRESSION_BOUND_PCT` | `10.0` | max allowed serving regression % |
| `XTRAIN_EXTRACT_PAGE_SIZE` | `100` | extraction pagination |

## SCRAPER_* (`xnch/config.py`, nested `ScraperSettings`)

| Variable | Default | Description |
|---|---|---|
| `SCRAPER_DEFAULT_TIER` | `auto` | fetch tier |
| `SCRAPER_MAX_CONCURRENT` | `5` | concurrency |
| `SCRAPER_REQUEST_TIMEOUT` | `30.0` | per-request timeout |
| `SCRAPER_INSTAGRAM_SESSION` | `""` | optional session cookie |
| `SCRAPER_TWITTER_USERNAME` / `_PASSWORD` / `_EMAIL` | `""` | optional credentials (env only) |

## Unprefixed & muse app

| Variable | Where | Purpose |
|---|---|---|
| `LITELLM_BASE_URL` | xnchat relay config | LiteLLM URL used by `/v1/chat/completions` relay |
| `LITELLM_API_KEY` | same | proxy auth (empty = none) |
| `XNCH_GATEWAY_URL` | muse (`web/`) | gateway proxy target; default `http://192.168.1.10:8001` |
| `XNCH_GATEWAY_SECRET` | muse + xnch | Hybrid-B minting secret (must match both sides) |
| `POSTGRES_PASSWORD`, `LANGFUSE_*`, `LITELLM_MASTER_KEY` | Node A compose env (`~/.xnch/xnch.env`) | container secrets — templates in `infra/no-k3s/shared/.env.example` |

## Hygiene notes

- `XNCH_POSTGRES_URL`'s in-source default contains embedded credentials — treat
  as a bug to fix upstream; always set the real DSN via env.
- Secrets belong only in `~/.xnch/xnch.env` / `~/.xnch/nexi.env` /
  `node-a/.env` (gitignored hosts files), never in the repo.
