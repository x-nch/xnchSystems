# xnch Configuration & Environment Variables

`xnch/config.py` declares a Pydantic `BaseSettings` model with
`env_prefix="XNCH_"` and `env_file=".env"`. Every field maps to an env var by
uppercasing the field name and prefixing `XNCH_` (e.g. `redis_url` →
`XNCH_REDIS_URL`). Fields with no explicit env prefix still follow the global
`XNCH_` prefix.

> Path defaults are relative to `~/.xnch` (via `XNCH_BASE_DIR`); all path
> properties derive from `base_dir`.

---

## Paths

| Env var | Field / property | Default |
|---------|------------------|---------|
| `XNCH_BASE_DIR` | `base_dir` | `~/.xnch` |
| (derived) | `keys_dir` | `{base_dir}/keys` |
| (derived) | `audit_dir` | `{base_dir}/audit` |
| (derived) | `db_path` | `{base_dir}/xnch.db` |
| (derived) | `governance_dir` | `{base_dir}/governance` |
| (derived) | `policies_dir` | `{base_dir}/policies` |
| (derived) | `weights_dir` | `{base_dir}/weights` |

---

## Core

| Env var | Field | Default | Notes |
|---------|-------|---------|-------|
| `XNCH_REDIS_URL` | `redis_url` | `redis://localhost:6379/0` | KV cache, sensory buffer, working memory |
| `XNCH_AUTH_SECRET` | `auth_secret` | `dev-secret-change-in-production` | HS256 secret for actor-token verification |
| `XNCH_TOKEN_TTL_MS` | `token_ttl_ms` | `30000` | |
| `XNCH_SESSION_TTL_S` | `session_ttl_s` | `120` | |
| `XNCH_RATE_LIMIT_PER_MINUTE` | `rate_limit_per_minute` | `10` | `/session/init` per-actor rate limit |
| `XNCH_NEXI_BASE_URL` | `nexi_base_url` | `http://localhost:8000` | Outbound `/session/start`, `/callback/outcome` |
| `XNCH_POSTGRES_URL` | `postgres_url` | `postgresql://xnch:…@localhost:5432/xnch` | pgvector episodic store, LangGraph checkpointer |

> **Security note:** the default `postgres_url` embeds a credential
> (`cf00d3e9…`) in source. Set `XNCH_POSTGRES_URL` in the environment / `.env`
> on gate7 and never commit real credentials.

---

## Learning

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_PATTERN_MIN_OBSERVATIONS` | `pattern_min_observations` | `10` |
| `XNCH_SCORE_ADAPTER_ACCURACY_THRESHOLD` | `score_adapter_accuracy_threshold` | `0.6` |
| `XNCH_MEMORY_RECALL_MIN_SCORE` | `memory_recall_min_score` | `0.35` |
| `XNCH_LEARNING_MODEL` | `learning_model` | `qwen2.5-vl-7b` |
| `XNCH_GRAPH_EXTRACTOR_MODEL` | `graph_extractor_model` | `ollama/phi3:mini` |

---

## Observability

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_LANGFUSE_PUBLIC_KEY` | `langfuse_public_key` | `""` |
| `XNCH_LANGFUSE_SECRET_KEY` | `langfuse_secret_key` | `""` |
| `XNCH_LANGFUSE_HOST` | `langfuse_host` | `https://cloud.langfuse.com` |
| `XNCH_LITELLM_PROXY_URL` | `litellm_proxy_url` | `http://litellm:4000` |

`xnch/routes/nexi_gateway.py` also reads the legacy env vars
`LITELLM_BASE_URL` and `LITELLM_API_KEY` / `LITELLM_MASTER_KEY` (not
`XNCH_`-prefixed).

---

## LangGraph HITL decision pipeline

| Env var | Field | Default | Notes |
|---------|-------|---------|-------|
| `XNCH_LANGGRAPH_PIPELINE` | `langgraph_pipeline` | `false` | Enables the LangGraph HITL surface (`/governance/pipeline/*`) |
| `XNCH_HITL_EXECUTION_MODE` | `hitl_execution_mode` | `always` | when-predicate for EXECUTION interrupt: `always` \| `risk_threshold` \| `never` |
| `XNCH_HITL_RISK_THRESHOLD` | `hitl_risk_threshold` | `0.5` | Used only in `risk_threshold` mode |

The pipeline runtime itself starts whenever the Postgres checkpointer is
available; the `langgraph_pipeline` flag marks it as the intended HITL path.
See [governance-hitl.md](governance-hitl.md).

---

## Perception

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_VAULT_DIR` | `vault_dir` | `~/.xnch/vault` |
| `XNCH_PERCEPTION_REDIS_DB` | `perception_redis_db` | `0` |
| `XNCH_ATTENTION_SILENCE_THRESHOLD_S` | `attention_silence_threshold_s` | `1.5` |
| `XNCH_ATTENTION_SCREEN_DIFF_THRESHOLD` | `attention_screen_diff_threshold` | `0.15` |
| `XNCH_ATTENTION_IDLE_TIMEOUT_S` | `attention_idle_timeout_s` | `600` |

---

## Filesystem MCP tool (read-only)

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_FS_POLICY_PATH` | `fs_policy_path` | `~/.xnch/fs-policy.yaml` |
| `XNCH_FS_LOCAL_HOST` | `fs_local_host` | `node-a` |
| `XNCH_FS_AGENT_NODE_B_URL` | `fs_agent_node_b_url` | `http://192.168.50.2:8003` |
| `XNCH_FS_AGENT_TOKEN` | `fs_agent_token` | `""` |
| `XNCH_FS_MAX_READ_BYTES` | `fs_max_read_bytes` | `2097152` |
| `XNCH_FS_MAX_LIST_ENTRIES` | `fs_max_list_entries` | `1000` |
| `XNCH_FS_MAX_GLOB_RESULTS` | `fs_max_glob_results` | `200` |

---

## Governed command execution MCP tool

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_EXEC_POLICY_PATH` | `exec_policy_path` | `~/.xnch/exec-policy.yaml` |
| `XNCH_EXEC_LOCAL_HOST` | `exec_local_host` | `node-a` |
| `XNCH_EXEC_AGENT_NODE_B_URL` | `exec_agent_node_b_url` | `http://192.168.50.2:8004` |
| `XNCH_EXEC_AGENT_TOKEN` | `exec_agent_token` | `""` |

---

## External MCP bridge

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_MCP_BRIDGE_ENABLED` | `mcp_bridge_enabled` | `true` |
| `XNCH_MCP_SERVERS_PATH` | `mcp_servers_path` | `~/.xnch/mcp-servers.yaml` |
| `XNCH_MCP_MAX_TOOL_ROUNDS` | `mcp_max_tool_rounds` | `3` |
| `XNCH_MCP_MAX_TOOL_ROUNDS_WITH_BRIDGE` | `mcp_max_tool_rounds_with_bridge` | `5` |

---

## Web search MCP tool

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_WEB_SEARCH_POLICY_PATH` | `web_search_policy_path` | `~/.xnch/web-search.yaml` |
| `XNCH_SEARXNG_URL` | `searxng_url` | `http://127.0.0.1:8888` |

---

## Memory routing

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_MEMORY_ROUTING_POLICY_PATH` | `memory_routing_policy_path` | `~/.xnch/memory-routing.yaml` |
| `XNCH_AM_PREFETCH_ENABLED` | `am_prefetch_enabled` | `false` | agentmemory lesson prefetch for `/nexi/chat` |

---

## Voice (STT + TTS)

| Env var | Field | Default |
|---------|-------|---------|
| `XNCH_VOICE_ENABLED` | `voice_enabled` | `true` |
| `XNCH_VOICE_STT_MODEL` | `voice_stt_model` | `base` |
| `XNCH_VOICE_STT_DEVICE` | `voice_stt_device` | `cpu` |
| `XNCH_VOICE_STT_COMPUTE_TYPE` | `voice_stt_compute_type` | `int8` |
| `XNCH_VOICE_STT_LANGUAGE` | `voice_stt_language` | `en` |
| `XNCH_VOICE_TTS_ENGINE` | `voice_tts_engine` | `piper` |
| `XNCH_VOICE_TTS_VOICE_PATH` | `voice_tts_voice_path` | `~/.xnch/voice/en_US-lessac-medium.onnx` |
| `XNCH_VOICE_TTS_CONFIG_PATH` | `voice_tts_config_path` | `~/.xnch/voice/en_US-lessac-medium.onnx.json` |
| `XNCH_VOICE_MAX_AUDIO_DURATION_S` | `voice_max_audio_duration_s` | `60.0` |
| `XNCH_VOICE_MAX_AUDIO_BYTES` | `voice_max_audio_bytes` | `10485760` |
| `XNCH_VOICE_MAX_TTS_CHARS` | `voice_max_tts_chars` | `2000` |
| `XNCH_VOICE_MODELS_DIR` | `voice_models_dir` | `~/.xnch/voice/models` |

---

## Suggested gate7 `.env` (non-secret example)

```env
XNCH_NEXI_BASE_URL=http://127.0.0.1:8000
XNCH_REDIS_URL=redis://localhost:6379/0
XNCH_POSTGRES_URL=postgresql://xnch:<redacted>@localhost:5432/xnch
XNCH_LANGGRAPH_PIPELINE=true
XNCH_HITL_EXECUTION_MODE=always
XNCH_AUTH_SECRET=<redacted>
```

## TODO

- `XNCH_VOICE_*` tuning values and the STT/TTS engine wiring are feature
  flags; exact runtime behavior of `/nexi/voice/*` needs verification against
  `xnch/voice/pipeline.py`.
- Confirm whether gate7 overrides any of these (e.g. `XNCH_HITL_EXECUTION_MODE=risk_threshold`)
  — this doc records code defaults only.
