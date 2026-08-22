# OpenCode handoff — Loop Engineering Phase 0+1

Work only Phase 0 + Phase 1. Do not start Phases 2–4.

## How this task is assigned

Primary: Cursor → **[opencode-mcp](https://github.com/AlaeddineMessadi/opencode-mcp)** → OpenCode serve (**Go**, not Zen pay-as-you-go).

```text
opencode_setup({ directory: "/Users/xnch/xnchSystems" })
opencode_fire({
  directory: "/Users/xnch/xnchSystems",
  agent: "build",
  providerID: "opencode-go",
  modelID: "kimi-k2.7-code",
  title: "loop-eng-phase0-1",
  prompt: "<this file body>"
})
# then opencode_check / opencode_wait / opencode_review_changes
```

Fallback CLI:

```bash
opencode run --dir /Users/xnch/xnchSystems --agent build \
  -m opencode-go/kimi-k2.7-code --title "loop-eng-phase0-1" \
  -f research/opencode-handoff-loop-engineering.md \
  -f research/loop-engineering-roadmap.md \
  "Execute Phase 0 + Phase 1 only per the attached handoff."
```

Note: `opencode/*` (e.g. `gpt-5.3-codex`) is **Zen credits**. Go models are `opencode-go/*` (kimi-k2.7-code, deepseek-v4-pro, qwen3.7-max, …). Connect via `/connect` → **OpenCode Go**.
## Auth note (human, not agent)

OpenCode Zen API keys belong in OpenCode Connect / `OPENCODE_API_KEY` env only — never commit keys into the repo, plan files, or chat logs. Rotate any key that was pasted into chat.

## Context files (read first)

1. `research/loop-engineering-roadmap.md` — the plan (source of truth)
2. `research/loop-engineering-and-evolutionary-optimization.md` — research backing
3. `AGENTS.md` — repo conventions

## Task

Implement **Phase 0 + Phase 1** from `research/loop-engineering-roadmap.md`.

### Phase 0

- Add `learning_model: str = "qwen2.5-vl-7b"` to `xnch/config.py` (`XNCH_LEARNING_MODEL`)
- Replace hardcoded `_LLM_MODEL = "ornith"` in `xnch/learning/policy_candidates.py` with `settings.learning_model`
- Align `beeai_model` default to the resident model if still `ornith`

### Phase 1

Critical correction: `xnch/agents/pipeline_graph.py` `create_pipeline()` is **never called**. Live chat is `nexi_gateway`; live decisions are `nexi/main.py` imperative. Hang the graph into xnch before resume wiring matters.

1. Add `xnch/agents/pipeline_runtime.py` owning `AsyncPostgresSaver` + compiled `create_pipeline(checkpointer=...)`
2. Init/teardown in `xnch/main.py` lifespan
3. Add routes:
   - `POST /governance/pipeline/invoke`
   - `POST /governance/pipeline/resume` using `Command(resume=...)`
4. Keep `nexi/main.py` imperative path as production default (do not replace yet)
5. Tests with `MemorySaver`: EXECUTION → interrupt → approve continues; reject → END

### Constraints

- Follow `AGENTS.md` import/style rules
- Do not add `deepagents` package
- Do not commit secrets (`.env`, API keys)
- Do not start Phase 2–4
- Prefer small, reviewable diffs; add tests for the resume path

### Done when

- Policy candidates uses configurable resident model (default qwen-vl)
- Invoke with an EXECUTION-shaped input returns a pending interrupt payload
- Resume approve/reject completes without crashing
- Unit tests cover interrupt → resume true/false
- Reply with: files changed, test commands, any blockers
