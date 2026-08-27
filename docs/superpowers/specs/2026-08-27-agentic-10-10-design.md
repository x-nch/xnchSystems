# Spec: xnchSystems Agentic Stack — "10/10" (MCP / Skills / Agentic)

- **Date:** 2026-08-27
- **Branch:** `feat/agentic-10-10`
- **Worktree:** `/Users/xnch/xnchSystems-agentic-10`
- **Status:** approved (user said "proceed")

## Goal

Bring the agentic tooling of `xnchSystems` to a defect-free, coherent, working
state across three surfaces:

1. **MCP** — one authoritative, machine-correct config; no broken/duplicate entries; graph stays fresh.
2. **Skills** — project-scoped engineering skills; marketing/SEO pack scoped out for this repo (globals untouched).
3. **Agentic** — a wired `review -> fix -> verify` loop around `code-review-graph`, reusable as a skill + agent + command.

"10/10" is defined operationally (acceptance criteria below), not as an absolute
score. Two honest, documented limitations are called out in §6.

## Current state (findings)

- Three conflicting MCP config files: `opencode.jsonc` (active), `.mcp.json`,
  `.opencode.json`.
- `opencode.jsonc` points `code-review-graph` at `/home/x-nch/xnchSystems` (Linux
  path — wrong on this Mac) and `xnch` MCP at
  `/home/x-nch/xnchSystems/.venv/bin/python` (does not exist here). Both MCPs are
  therefore broken on this machine.
- Marketing/SEO skills (`ad-creative`, `seo-audit`, `cold-email`, ...) live in
  `/Users/xnch/.agents/skills` and `/Users/xnch/.claude/skills`, injected by the
  harness globally — not controllable from repo config alone.
- No wired agentic loop; `code-review-graph` graph decays if not rebuilt.
- Submodule pointers for `nexi`/`xnch` were stale/unfetchable upstream; resolved in
  the worktree by checking out the parent-recorded commits from local caches.

## Plan

### 0. Worktree + submodules (done)
- Branch `feat/agentic-10-10` off `feat/ornith-phase1`.
- Worktree at `/Users/xnch/xnchSystems-agentic-10`.
- Submodules initialized: `mcp/superpowers-mcp`, `nexi`, `xnch`, `skills/superpowers`
  — all populated and pointer-consistent with the parent branch.

### 1. MCP — single source of truth, mac-correct
- Rewrite project `opencode.jsonc` as the only project MCP authority. Entries:
  - `code-review-graph` — `uvx code-review-graph serve --repo /Users/xnch/xnchSystems` (fix path).
  - `xnch` — `/Users/xnch/xnchSystems/.venv/bin/python -m xnch_mcp` with `XNCH_BASE_URL`/`XNCH_ACTOR` (fix path).
  - `superpowers` — `node ./mcp/superpowers-mcp/build/index.js` with `SUPERPOWERS_SKILLS_DIR=./skills/superpowers/skills` and `SUPERPOWERS_USE_LOCAL_SKILLS=true`.
  - `agentmemory` — `npx -y @agentmemory/mcp` with `AGENTMEMORY_URL`/`AGENTMEMORY_SECRET`.
  - `langchain-docs` — remote `https://docs.langchain.com/mcp`.
  - `figma` — kept only if `FIGMA_API_KEY` env is present; otherwise `enabled:false`.
- Remove/`.bak` the conflicting `.mcp.json` and `.opencode.json` so there is exactly
  one project MCP config.
- **Auto-rebuild graph:** add `scripts/build-crg.sh` (builds/incremental-updates the
  `code-review-graph` graph for this repo) and wire it via a `sessionStart` hook (or a
  documented cron/commit hook) so the graph never goes stale.
- Verify each server starts and returns tools.

### 2. Skills — project-scoped engineering set
- Add `.opencode/skills/` with curated engineering skills:
  - Link relevant superpowers skills: `systematic-debugging`,
    `test-driven-development`, `writing-plans`, `using-git-worktrees`,
    `requesting-code-review`, `receiving-code-review`, `verification-before-completion`.
  - Add `code-review-graph` usage skill (documents the graph MCP tools).
  - Add `review-loop` skill (see §3).
- Add `.opencode/rules/skills-scope.md` declaring marketing/SEO/growth skills
  **out of scope** for this repo, plus an AGENTS.md note, so project instructions are
  authoritative.
- **Honest limit:** if the harness keeps injecting `~/.agents/skills` globally, the
  project rule makes them non-firing here; globals are NOT deleted. Verification step
  confirms whether opencode honors project-only skill loading.

### 3. Agentic — wired review->fix->verify loop
- New skill `.opencode/skills/review-loop/SKILL.md`:
  1. `code-review-graph.detect_changes` on the diff (base = merge-base/main).
  2. Route risk items to `devtools/code-reviewer` (and `ai/ml-engineer` for ML code) subagents.
  3. Apply fixes; run `pytest` (nexi/tests, xnch/tests, tests/).
  4. Re-run `detect_changes`; confirm zero high-risk items.
  5. Emit report.
- New agent `.opencode/agents/reviewer.md` (mode: subagent) that owns the loop.
- Optional `/review` command in `.opencode/commands/review.md` to trigger it.

## Acceptance criteria

- [ ] All MCP servers declared in `opencode.jsonc` start cleanly on this Mac; no
      `/home/x-nch/...` paths remain; no duplicate/conflicting MCP config files.
- [ ] `code-review-graph` graph builds on `sessionStart`/commit; `detect_changes`
      returns results on a sample diff.
- [ ] `review-loop` skill + `reviewer` agent exist; running it on a sample diff yields
      a fix+verify report (or an explicit "no high-risk findings" result).
- [ ] Project `.opencode/skills/` + `.opencode/rules/skills-scope.md` scope skills to
      engineering; global marketing pack untouched but non-firing here.
- [ ] Worktree submodules remain consistent (`git submodule status` clean).

## Documented limitations (not papered over)

1. Global skill injection is harness-controlled. We scope at the project level via
   rules/instructions; we cannot guarantee the harness stops loading `~/.agents/skills`.
2. "10/10" = zero concrete defects + coherent wiring + a working loop, not an objective
   absolute score. The earlier 8/10 "graph decay" risk is mitigated by the auto-rebuild
   hook but still depends on that hook running.

## Files touched

- `opencode.jsonc` (rewrite)
- `.mcp.json`, `.opencode.json` (removed/backup)
- `scripts/build-crg.sh` (new)
- `.opencode/skills/**` (new: engineering skill links + review-loop + code-review-graph)
- `.opencode/rules/skills-scope.md` (new)
- `.opencode/agents/reviewer.md` (new)
- `.opencode/commands/review.md` (new, optional)
- `AGENTS.md` (scope note, optional)
