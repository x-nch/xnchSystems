# Nexi configuration

Settings live in `nexi/config.py` as a Pydantic `BaseSettings` class with
`env_prefix = "NEXI_"` and `env_file = ".env"` (relative to the working
directory). Env var names are `NEXI_<FIELD>` — e.g. `NEXI_XNCH_BASE_URL`.

At import time nexi instantiates `settings = Settings()`; config is read once at
process start (no runtime reload).

## Settings table

| Env var | Field | Default | Purpose |
|---------|-------|---------|---------|
| `NEXI_XNCH_BASE_URL` | `xnch_base_url` | `http://localhost:8001` | Base URL for `XnchClient` (xnch control plane). In production on Node B this is the Node A link address `http://192.168.50.1:8001` |
| `NEXI_XNCH_PUBLIC_KEY_PATH` | `xnch_public_key_path` | `~/.xnch/keys/public.pem` | Path to xnch public key (token verification). TODO: not referenced by current code paths in this package |
| `NEXI_VLLM_PRIMARY_URL` | `vllm_primary_url` | `http://192.168.50.2:8083/v1` | Primary vLLM endpoint (Qwen-VL on Node B), option-generation fallback |
| `NEXI_VLLM_PRIMARY_TIMEOUT_S` | `vllm_primary_timeout_s` | `30.0` | Timeout for primary vLLM call |
| `NEXI_VLLM_SECONDARY_URL` | `vllm_secondary_url` | `""` | Secondary vLLM endpoint (unused — empty) |
| `NEXI_VLLM_SECONDARY_TIMEOUT_S` | `vllm_secondary_timeout_s` | `45.0` | Timeout for secondary vLLM call |
| `NEXI_MODEL_ID` | `model_id` | `qwen2.5-vl-7b` | Default model id (used by eval LLM-judge path) |
| `NEXI_OPTIONS_COUNT` | `options_count` | `5` | Number of PlanOptions generated per decision (`generate_options`) |
| `NEXI_LITELLM_PROXY_URL` | `litellm_proxy_url` | `http://localhost:4000/v1` | LiteLLM proxy base for intent classification + option generation |
| `NEXI_LITELLM_PROXY_TIMEOUT_S` | `litellm_proxy_timeout_s` | `60.0` | Timeout for LiteLLM calls |
| `NEXI_INTENT_CLASSIFIER_MODEL` | `intent_classifier_model` | `qwen2.5-vl-7b` | Model used by the intent classifier |
| `NEXI_SESSION_TTL_S` | `session_ttl_s` | `120` | Session TTL (seconds) |
| `NEXI_CLARIFICATION_TTL_S` | `clarification_ttl_s` | `120` | Clarification TTL (seconds) |
| `NEXI_EXECUTION_TOKEN_TTL_MS` | `execution_token_ttl_ms` | `30_000` | Execution token TTL (ms) |
| `NEXI_REDIS_URL` | `redis_url` | `unix:///tmp/xnch-redis.sock` | Redis URL (KV cache, shared with xnch) |
| `NEXI_EXECUTION_RUNNER_URL` | `execution_runner_url` | `http://192.168.50.1:8001/execution` | Execution runner base — nexi posts `/execute` here; default points at xnch's stub runner on Node A |
| `NEXI_VLLM_HEALTH_URL` | `vllm_health_url` | `http://192.168.50.2:8083/health` | vLLM health endpoint (used by proactivity engine) |
| `NEXI_AUDIT_EVENTS_PATH` | `audit_events_path` | `~/.xnch/audit/events.jsonl` | Audit events file path. TODO: actual audit emission goes through xnch's PG `audit_events` store, not this file |
| `NEXI_CAPABILITIES_GENERATED_PATH` | `capabilities_generated_path` | `~/.xnch/nexi-capabilities.generated.yaml` | Where the auto-generated capabilities overlay is written (atomic tmp+rename) |
| `NEXI_MCP_SERVERS_PATH` | `mcp_servers_path` | `~/.xnch/mcp-servers.yaml` | MCP bridge server inventory (fallback source for bridged tools) |
| `NEXI_INFRA_MANIFESTS_PATH` | `infra_manifests_path` | `<repo>/infra/no-k3s` | Directory of systemd/compose manifests used by service discovery |
| `NEXI_EXEC_POLICY_PATH` | `exec_policy_path` | `~/.xnch/exec-policy.yaml` | Governed exec policy (allowed prefixes, denied substrings) |
| `NEXI_FS_POLICY_PATH` | `fs_policy_path` | `~/.xnch/fs-policy.yaml` | Governed filesystem policy (roots, deny globs) |
| `NEXI_CAPABILITY_REFRESH_INTERVAL_S` | `capability_refresh_interval_s` | `300` | Interval between full capability refreshes (overlay write) |
| `NEXI_PROBE_INTERVAL_S` | `probe_interval_s` | `60` | Interval between live service health probes |
| `NEXI_PROBE_TIMEOUT_S` | `probe_timeout_s` | `2.0` | Per-probe HTTP timeout (seconds) |
| `NEXI_XNCH_TOOLS_ENDPOINT` | `xnch_tools_endpoint` | `/nexi/tools` | xnch path for tool inventory (authoritative source) |
| `NEXI_CAPABILITY_AUTO_REFRESH` | `capability_auto_refresh` | `true` | Enable the startup + periodic capability refresh loop |

## Config consumed from xnch (not NEXI_*)

Some settings are imported directly from the **xnch** package rather than from
nexi's own settings:

| xnch setting | Used by | Notes |
|--------------|---------|-------|
| `xnch.config.settings.redis_url` | `intent_interpreter._get_redis` | Intent classification cache (key `xnch:intent:<sha256>`) |
| `xnch.config.settings.litellm_proxy_url` | `eval/grader.llm_judge` | LLM-judge endpoint override |

## Other env vars read ad-hoc

| Env var | Read in | Notes |
|---------|---------|-------|
| `XNCH_MEMORY_RECALL_MIN_SCORE` | `nexi/pipeline/context_assembler.py` | Default recall similarity threshold (default `0.35`) |

## Shipped artifacts

| Path | Purpose |
|------|---------|
| `nexi/weights/EXECUTION-wc-v1.0.yaml` | Local EXECUTION weight profile (`wc-v1.0`) — `policy_score 0.25, outcome_score 0.30, risk_score 0.35, context_fit_score 0.10` |
| `nexi/weights/QUERY-wc-v1.0.yaml` | Local QUERY weight profile — `policy_score 0.20, outcome_score 0.30, risk_score 0.20, context_fit_score 0.30` |
| `nexi/policies/default.yaml` | Baseline governance rules shipped for reference (weekend-deploy block, viewer read-only, etc.) — **live evaluation is on xnch** |
| `nexi/character/persona.yaml`, `capabilities.yaml`, `identity_facts.yaml` | Persona/capability/fact sources for the chat system prompt (loaded via `prompt_loader`) |

> Weight profiles are consumed from xnch at runtime (`GET /governance/weights?intent_class=…`);
> the YAML files above document the intended format and serve as the shipped
> fallback reference. Only EXECUTION and QUERY profiles are shipped; DECISION and
> ESCALATION use `_DEFAULT_WEIGHTS` in `nexi/pipeline/evaluator.py` when xnch
> weights are unavailable.
