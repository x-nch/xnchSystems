# Memory routing — deploy & verify (gate7)

Operational runbook for **dual memory**: pgvector episodic (`xnch_memory_*`) vs
agentmemory (`am_memory_*`).

- Conceptual guide: [Memory routing guide](../guides/memory-routing.md)
- Tool catalog: [mcp-tools.md](../reference/mcp-tools.md)
- Config reference: [mcp-config.md](../reference/mcp-config.md#memory-routingyaml)

---

## Mental model

| Store | Backend | Auto in chat? | Use for |
|-------|---------|---------------|---------|
| **Episodic** | Postgres pgvector | Yes — recall + post-turn store | Chat history, identity, “what did we discuss?” |
| **Curated** | agentmemory `:3111` | No (optional prefetch) | Deploy lessons, architecture, action items |

They **do not sync**. Never save the same fact to both.

---

## 1. Deploy policy

```bash
cp infra/no-k3s/shared/memory-routing.example.yaml ~/.xnch/memory-routing.yaml
sudo systemctl restart xnch.service
```

Default blocks `nexi` from `xnch_memory_store_note` (see `deprecate_store_note_for`).

Optional lesson prefetch (off by default):

```bash
# append to ~/.xnch/xnch.env
XNCH_AM_PREFETCH_ENABLED=true
sudo systemctl restart xnch.service
```

Prefetch injects up to 2 lessons from `am_memory_lesson_recall` into the system
prompt (`## Agent lessons (curated)`). Fail-open if agentmemory is down.

---

## 2. Prerequisites

| Component | Check |
|-----------|-------|
| xnch | `systemctl is-active xnch.service` |
| Postgres pgvector | episodic recall works |
| agentmemory | `systemctl is-active agentmemory.service` + `:3111` |
| MCP bridge | `am_*` tools connected (`python -m cli mcp servers`) |

```bash
systemctl is-active xnch.service agentmemory.service
curl -s http://127.0.0.1:3111/health 2>/dev/null || true
```

---

## 3. Verify routing (CLI)

```bash
cd /home/x-nch/xnchSystems
PY=/home/x-nch/xnchSystems/xnch/.venv/bin/python
export PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch

# Nexi blocked from pgvector manual notes
$PY -m cli mcp call xnch_memory_store_note --arg text="test" --actor nexi
# expect HTTP 403

# Operator can still write pgvector notes
$PY -m cli mcp call xnch_memory_store_note --arg text="operator note" --actor operator
# expect status: ok

# Episodic recall (pgvector)
$PY -m cli mcp call xnch_memory_recall --arg query="deploy" --arg top_k=3

# Curated recall (agentmemory)
$PY -m cli mcp call am_memory_lesson_recall --arg query="MCP bridge" --arg limit=2
```

---

## 4. Verify routing (curl)

```bash
# 403 for nexi + store_note
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_memory_store_note","arguments":{"text":"lesson"}}'

# episodic recall
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_memory_recall","arguments":{"query":"MCP bridge","top_k":3}}' | jq .

# curated lesson recall
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"am_memory_lesson_recall","arguments":{"query":"CRG graph","limit":2}}' | jq .
```

---

## 5. Verify Nexi chat routing

```bash
$PY -m cli chat --session mem-routing-test \
  "Which tool saves a deploy lesson — xnch_memory_store_note or am_memory_lesson_save? Tool name only."

$PY -m cli chat --session mem-routing-test2 \
  "For chat history recall, xnch_memory_recall or am_memory_recall? One word."
```

**Expected:** `am_memory_lesson_save` and `xnch_memory_recall`.

---

## 6. Audit overlap (optional)

Detect duplicate facts across stores:

```bash
PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch \
  python scripts/audit-memory-overlap.py --limit 15
```

---

## 7. Unit tests

```bash
pytest xnch_mcp/tests/test_memory_routing.py xnch/tests/test_memory_routing_policy.py -q
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Nexi still calls `store_note` | Old xnch not restarted | `sudo systemctl restart xnch.service` |
| `am_*` tools missing | Bridge / agentmemory down | `systemctl start agentmemory`; check `mcp servers` |
| Chat has no lessons block | Prefetch disabled | Set `XNCH_AM_PREFETCH_ENABLED=true` |
| Duplicate facts in both stores | Pre-routing saves | Run audit script; use `am_*` for new curated facts |
| `xnch_memory_recall` empty | No similar episodes / min score | Lower `XNCH_MEMORY_RECALL_MIN_SCORE` or chat more |

---

## See also

- [MCP bridge deploy](mcp-bridge-deploy.md) — bridge + agentmemory connection
- [Nexi test prompts](../guides/nexi-test-prompts.md) — memory routing prompts
- [mcp-http-api.md](../reference/mcp-http-api.md) — audit `memory_target` field
