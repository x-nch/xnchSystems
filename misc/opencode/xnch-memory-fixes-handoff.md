# OpenCode handoff: Nexi chat / memory context fixes

Copy everything below the line into a new OpenCode session.

---

## Task

Fix **server-side memory context** for `/nexi/chat` so Nexi stops fixating on stale test junk ("Build something") and reliably surfaces identity facts (XNCH, Nexi, stack). **Web UI and MCP are out of scope** — do not build those.

Repo: `/home/x-nch/xnchSystems`. Read `AGENTS.md`. Use `code-review-graph` MCP before Grep/Glob/Read.

## Background

Full analysis: `misc/notes/nexi-chat-memory-context-gap.md`

**Symptom:** User asks what to build / to recall memory. Nexi repeats "Build something" and asks for a project name despite identity facts existing in Postgres.

**Context pipeline today:**

```
POST /nexi/chat
  → assemble_context()          # nexi/pipeline/context_assembler.py
      → working_memory.get_turns(session_id, last_n=20)
      → pg_episodic.retrieve_similar(query=message, top_k=5, min_score=0.0)
      → build_system_prompt(session_memory=episode summaries)
  → LiteLLM/Ornith
  → store_episode(summary=f"OpenClaw chat: {user_msg[:100]}")  # junk summaries
```

## Already done (do not redo)

### CLI (complete)
- `chat --new-session`, REPL defaults fresh session, `--continue` to reuse
- `session show` / `session clear`
- REPL `/recall` → calls `/nexi/memory/recall` (CLI-side only)
- See `misc/opencode/xnch-cli-handoff.md`

### Server (complete)
- Thinking block sanitization: `xnch/routing/response_sanitize.py` + `nexi_gateway.py`

## Server fixes to implement (priority order)

### P0 — Context assembly quality

**File:** `nexi/pipeline/context_assembler.py`

1. **`min_score` filter** — pass `min_score` to `retrieve_similar` (default ~0.35–0.4, configurable via `XNCH_*` or `NEXI_*` setting). Drop weak matches like 0.24 "Build something" noise.

2. **Inject identity facts every turn** — always include `type=identity` episodes in system prompt (not only when semantic search hits). Options:
   - Add `PgEpisodicStore.fetch_by_type("identity", limit=20)` and call from `assemble_context`
   - Or load from `nexi/character/cold_start_seeder.py` `IDENTITY_FACTS` + `nexi_character.yaml` `memory_identity.knows_about`
   - Add `## Identity` section in `build_system_prompt()` separate from `## Session Context`

3. **Better episode text for context** — stop preferring useless summaries. Add helper e.g. `_episode_context_line(ep)`:
   - If `summary` starts with `OpenClaw chat:` → use truncated `raw_text` instead
   - Else prefer `summary` if substantive, else `raw_text[:300]`
   - Dedupe identical context lines before injecting (same as CLI `dedupe_memory_results`)

4. **Tests** — extend `nexi/tests/test_context_assembler.py`:
   - Identity always present when `fetch_by_type` returns facts
   - Low-similarity episodes filtered
   - Junk summary replaced by raw_text

### P1 — Episode storage

**File:** `xnch/routes/nexi_gateway.py` (both `/chat` and `/chat/stream`)

5. **Better summaries on store** — replace:
   ```python
   summary=f"OpenClaw chat: {body.message[:100]}"
   ```
   With something useful, e.g.:
   ```python
   summary=f"{body.message[:80]} → {response_text[:120]}"
   ```
   Or first line of assistant response only. Keep `raw_text` as full `user\nassistant`.

6. **Dedupe on store (optional, small scope)** — before `store_episode`, skip if an episode with identical `raw_text` exists in last N hours (query or hash). Prevents e2e test pollution. Add test in `xnch/tests/` or `tests/test_nexi_gateway.py`.

### P2 — Working memory hygiene

**File:** `xnch/memory/working_memory.py`

7. **TTL on turn lists** — `append_turn` should `EXPIRE` `session:{id}:turns` (use `settings.session_ttl_s` or new `working_memory_ttl_s`, default 86400). Prevents infinite Redis growth when CLI reuses sessions with `--continue`.

8. **Test** in `xnch/tests/test_working_memory.py` — verify expire is set (mock redis `expire` called).

### P3 — Chat recall routing (server-side, optional if time)

**File:** `xnch/routes/nexi_gateway.py` or `assemble_context`

9. When user message matches recall intent (`/recall`, `recall memory`, `memory recall` — reuse pattern from `cli/util.py` `parse_recall_intent` or share a small `nexi/utils/recall_intent.py`), **prepend** explicit recall results into system prompt or return structured recall block before LLM call. CLI already handles this client-side; server fix makes OpenClaw/curl benefit too.

### Out of scope
- Web UI
- MCP host / tool loop
- Graph extraction / consolidation job fixes
- New CLI commands

## Key files

```
nexi/pipeline/context_assembler.py    # main fix target
nexi/character/prompt_loader.py       # add Identity section
nexi/character/cold_start_seeder.py   # IDENTITY_FACTS reference
nexi/character/nexi_character.yaml    # memory_identity.knows_about
xnch/routes/nexi_gateway.py           # episode store summaries
xnch/memory/pg_episodic_store.py      # add fetch_by_type if needed
xnch/memory/working_memory.py          # TTL on turns
xnch/config.py                        # min_score, ttl settings
cli/util.py                           # parse_recall_intent (reference only)
misc/notes/nexi-chat-memory-context-gap.md
```

## Config suggestions

Add to `xnch/config.py` (or `nexi/config.py` if more appropriate):

```python
memory_recall_min_score: float = 0.35
working_memory_ttl_s: int = 86400
```

Env: `XNCH_MEMORY_RECALL_MIN_SCORE`, `XNCH_WORKING_MEMORY_TTL_S`

## Verify

```bash
cd /home/x-nch/xnchSystems
source .venv/bin/activate
pytest nexi/tests/test_context_assembler.py xnch/tests/test_working_memory.py tests/test_nexi_gateway.py -q
# restart xnch after changes:
sudo systemctl restart xnch
python -m cli chat --new-session
# Ask: "what should we build next" — should reference XNCH/Nexi identity, not "Build something"
python -m cli memory recall build something   # confirm pollution still in DB but filtered from prompt
```

## Acceptance criteria

- [ ] `assemble_context` filters episodes below `min_score`
- [ ] Identity facts appear in system prompt every chat turn (test asserts)
- [ ] Episode context lines use meaningful text, not `OpenClaw chat: …` junk
- [ ] New chat episodes store better summaries
- [ ] Working memory turns get Redis TTL
- [ ] Existing tests pass; new tests for above behaviors
- [ ] Update `misc/notes/nexi-chat-memory-context-gap.md` checkboxes for completed items
- [ ] No commit unless asked

## Production context (gate7)

- xnch `:8001`, nexi on node-b `:8000`
- Postgres episodic store has duplicate `"Build something"` test episodes (~0.24 similarity)
- Identity episodes seeded at boot via `seed_identity_memories()` in `xnch/main.py` lifespan

Start by reading `context_assembler.py` and `prompt_loader.py`, then implement P0.
