# Nexi chat / memory context gap (2026-08-02)

Observed during CLI `python -m cli chat` session on gate7.

## Symptom

User asks what to build next / to recall memory. Nexi fixates on repeated
"Build something" and keeps asking for a project name, despite identity
facts about XNCH/Nexi existing in the system.

## Root causes

1. **Sticky CLI session** — `~/.xnch/cli_state.json` reuses one `session_id`;
   Redis working memory accumulates all REPL turns (no TTL on turn lists).
2. **Episodic pollution** — e2e/stream tests stored many identical
   `"Build something"` conversation episodes; semantic recall returns them
   at low similarity (~0.24) with no `min_score` filter in context assembly.
3. **Poor episode summaries** — stored as `OpenClaw chat: {user_msg}`; context
   assembler prefers `summary` over `raw_text`, so model sees junk bullets.
4. **Identity facts not always in prompt** — `cold_start_seeder` identity
   episodes only appear when semantic search matches; not injected every turn.
5. **Chat ≠ memory recall** — saying "recall memory" in chat does not call
   `/nexi/memory/recall`; only embedding search on the literal user message.

## Context pipeline

`/nexi/chat` → `assemble_context` → working memory (last 20 turns) +
`pg_episodic.retrieve_similar(query=current message, top_k=5)` → system prompt
+ message history → LiteLLM/Ornith.

## Workarounds

```bash
rm ~/.xnch/cli_state.json
python -m cli chat --session "cli-$(date +%s)"
python -m cli memory recall nexi xnch   # direct API, not chat
```

## Proposed fixes

### CLI (done — see misc/opencode/xnch-cli-handoff.md)

- [x] CLI `chat --new-session` (fresh session per REPL; `--continue` to reuse)
- [x] Route explicit "recall memory" intents in REPL (`/recall`, `recall memory`, …)

### Server (OpenCode handoff: misc/opencode/xnch-memory-fixes-handoff.md)

- [ ] TTL on working-memory turn keys
- [ ] Inject identity facts into every system prompt
- [ ] Better episode summaries (or use truncated `raw_text`)
- [ ] `min_score` threshold in `assemble_context`
- [ ] Dedupe identical episodes on store or in recall
- [ ] Server-side recall intent in `/nexi/chat` (optional; CLI done client-side)
- [ ] Store project goals/milestones as typed episodes when decided

## Key files

- `nexi/pipeline/context_assembler.py`
- `xnch/routes/nexi_gateway.py` (episode store + chat)
- `xnch/memory/working_memory.py`
- `nexi/character/cold_start_seeder.py`
- `cli/client.py` (`~/.xnch/cli_state.json` session persistence)
