# Chat & Tools

Audience: users/devs driving the agent. Sources: `xnch/routes/chat.py`,
`xnch_mcp/`, guides kept alongside:
[test prompts](nexi-test-prompts.md) ·
[memory routing](memory-routing.md) · [MCP CLI](mcp-cli.md) ·
[bridge architecture](../architecture/mcp-bridge.md).

## Talking to the agent

| Surface | Command | Use for |
|---|---|---|
| CLI REPL | `uv run xnch-cli chat --new-session` | interactive sessions with persisted context |
| CLI one-shot | `uv run xnch-cli chat "..."` | scripted probes |
| HTTP | `POST /nexi/chat` / `/nexi/chat/stream` | apps, muse, SSE clients |
| OpenAI clients | `POST /v1/chat/completions` (`model: qwen3-xml`) | plain completions via litellm relay — no memory/tools |
| Voice | `cli voice talk` or `/nexi/voice/chat` | push-to-talk loop ([voice](voice.md)) |

## What the tool loop can touch

- Native `xnch_*`: memory recall/store (`xnch_memory_*`), governed exec
  (`xnch_exec_run` — ExecPolicy-confined), web search (`xnch_web_search` →
  SearXNG).
- Bridged: `crg_*` code-graph reads, `am_*` curated agentmemory,
  `doc_*` offline docs. Round cap 3 (5 with bridge active).

Routing discipline (episodic vs curated, exec vs read-only) is enforced by
tiers + actors and taught to the model via persona `tool_routing`
([tier matrix](../architecture/mcp-bridge.md#actor--tier-model)). Verify routing
behavior with the copy-paste catalog: [nexi-test-prompts](nexi-test-prompts.md).

## Model routing

`classify_request` picks between local ornith and the judgment path; intent
classification uses `NEXI_INTENT_CLASSIFIER_MODEL`; consolidation's extractor
uses `XNCH_GRAPH_EXTRACTOR_MODEL`. All default to local-first
([env reference](../reference/env-vars.md)).

## Memory behavior in chat

Every turn auto-injects L2 pgvector recall (top_k 5, min 0.35) + L1 turns +
entity graph context; curated `am_*` memories are **explicit tool calls only**
— never auto-injected. Configure the boundary via
`~/.xnch/memory-routing.yaml`: [memory-routing guide](memory-routing.md) and its
[deploy runbook](../runbooks/memory-routing-deploy.md).

## Quick drills after deploy

```bash
uv run xnch-cli mcp servers        # bridge inventory connected?
uv run xnch-cli mcp test           # canned routing tests
./infra/no-k3s/e2e-test.sh              # full-stack smoke
```
