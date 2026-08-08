# Memory routing — xnch episodic vs agentmemory

Nexi has **two memory systems**. They do not sync. Pick the right one.

**Deploy runbook:** [memory-routing-deploy.md](../runbooks/memory-routing-deploy.md)

## Contents

- [Mental model](#mental-model)
- [What runs automatically](#what-runs-automatically)
- [Tool routing](#tool-routing)
- [Actor restrictions](#actor-restrictions)
- [Policy & prefetch](#policy--prefetch)
- [Audit & tests](#audit--tests)
- [See also](#see-also)

---

## Mental model

| | **Diary** (`xnch_memory_*`) | **Notebook** (`am_memory_*`) |
|--|------------------------------|------------------------------|
| **Backend** | Postgres pgvector (gate7) | agentmemory `:3111` |
| **Primary?** | Yes — runtime brain | No — curated ops memory |
| **Auto in `/nexi/chat`?** | Recall + store each turn | Only if prefetch enabled |
| **Best for** | “What did we discuss?” | Deploy lessons, architecture, actions |

Historical note: pgvector **replaced** agentmemory/ChromaDB for core episodic recall.
`am_*` returned via the MCP bridge for **structured agent memory**, not chat logs.

---

## What runs automatically

Every `POST /nexi/chat` turn (no tool call required):

1. **`assemble_context`** — `pg_episodic.retrieve_similar()` injects relevant episodes
   into the system prompt.
2. **Post-reply store** — user message + assistant reply saved as `conversation`
   episode in pgvector (unless blocked by memory guard or duplicate within 24h).

Agentmemory is **not** queried unless:

- Nexi calls an `am_*` tool during the tool loop, or
- `XNCH_AM_PREFETCH_ENABLED=true` (injects up to 2 lessons at context build time).

---

## Tool routing

| Need | Tool | Not |
|------|------|-----|
| Chat / session recall | `xnch_memory_recall` | `am_memory_recall` |
| Pending proactivity | `xnch_memory_surface` | — |
| Save deploy lesson | `am_memory_lesson_save` | `xnch_memory_store_note` |
| Save architecture fact | `am_memory_save` | `xnch_memory_store_note` |
| Recall lessons | `am_memory_lesson_recall` | `xnch_memory_recall` |
| Track work item | `am_memory_action_create` | — |
| Manual pgvector note | `xnch_memory_store_note` | **operator/opencode only** |

**Never** save the same fact to both stores.

---

## Actor restrictions

`~/.xnch/memory-routing.yaml` → `deprecate_store_note_for: [nexi]`.

| Actor | `xnch_memory_store_note` | `am_memory_save` |
|-------|--------------------------|------------------|
| `nexi` | **403 blocked** | ✓ |
| `operator` | ✓ | ✓ |
| `opencode` | ✓ | — (no bridged tools) |

Nexi still has full access to `xnch_memory_recall` and all `am_*` tools.

---

## Policy & prefetch

```bash
cp infra/no-k3s/shared/memory-routing.example.yaml ~/.xnch/memory-routing.yaml
```

Optional prefetch in `~/.xnch/xnch.env`:

```bash
XNCH_AM_PREFETCH_ENABLED=true   # default false
```

Adds `## Agent lessons (curated)` to the system prompt via `am_memory_lesson_recall`
(max 2 lessons × 250 chars). Skipped silently if agentmemory is unreachable.

Restart after changes: `sudo systemctl restart xnch.service`

---

## Audit & tests

```bash
# overlap check
PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch \
  python scripts/audit-memory-overlap.py

# unit tests
pytest xnch_mcp/tests/test_memory_routing.py -q

# E2E routing
python -m cli mcp call xnch_memory_store_note --arg text=x --actor nexi  # 403
python -m cli chat --session t "Which tool saves a deploy lesson? Name only."
```

MCP audit events for memory tools include `memory_target: episodic|agentmemory`.

---

## See also

- [mcp-tools.md](../reference/mcp-tools.md) — catalog + actor matrix
- [mcp-http-api.md](../reference/mcp-http-api.md) — HTTP examples + audit fields
- [mcp-config.md](../reference/mcp-config.md) — env vars
- [nexi-test-prompts.md](nexi-test-prompts.md) — copy-paste chat prompts
