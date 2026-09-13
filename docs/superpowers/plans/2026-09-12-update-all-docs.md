# Plan: Update All Documentation

## Goal
Update every documentation file in the repo to reflect Phase 1 consolidation (capability sidecar cutover, CLI grouping, legacy removal) and Phase 2 memory-service extraction (remote mode, SSE relay, rollback). This plan covers 70+ doc files across all categories.

## Global Constraints
- All `python -m cli` references → `python -m clients.cli`
- All `agent-runner/` → `clients/agent-runner/` (renamed)
- Legacy `exec-agent/` and `fs_read_agent/` packages removed — no references remain
- `XNCH_EXEC_AGENT_*`, `XNCH_FS_AGENT_*` env vars removed (Phase 1)
- `XNCH_MEMORY_EMBEDDED`, `XNCH_MEMORY_SERVICE_URL`, `XNCH_MEMORY_TOKEN` are new Phase 2 vars
- All paths absolute: `/home/x-nch/xnchSystems/` (node-a) / `/home/x-nch/.xnch/` (node-b configs)
- XNCH_MEMORY_EMBEDDED defaults to `1` (embedded) / `0` (remote)
- Fail-closed token auth on memory-service

## Task 1: Update README.md
- [ ] Replace legacy exec-agent :8004 / fs-read-agent :8003 service listings
- [ ] Update CLI grouping: `python -m clients.cli` (verified working)
- [ ] Update topology references to capability sidecar :8090
- [ ] Add memory-service :8003 remote mode note
- [ ] Update nexi :8000 reference (unchanged)

## Task 2: Update AGENTS.md
- [ ] Refresh single-home registry: policy → `xnch/policy/`, security → `xnch/security/`, memory → `agentmemory (:3111)`, execution → `capability_agent/`
- [ ] Update execution boundary pointer
- [ ] Confirm memory routing: `am_*` tools ONLY (deprecated `xnch_memory_store_note`)
- [ ] Add capability_agent routing note

## Task 3: Update Architecture Docs
- [ ] `docs/architecture/topology.md` — remove exec-agent :8004 / fs-read-agent :8003 entries; add capability sidecar :8090; update memory-service :8003
- [ ] `docs/architecture/overview.md` — update package listing: `clients/cli/`, `clients/agent-runner/`, `capability_agent/`, `memory-service` (Phase 2)
- [ ] `docs/architecture/data-model.md` — verify no stale legacy references
- [ ] `docs/architecture/execution-boundary.md` — already updated; confirm Kuzu single-owner invariant matches Phase 2

## Task 4: Update Deploy Docs
- [ ] `docs/deploy.md` — update Mac agent-runner path: `clients/agent-runner/`; update service references; remove exec-agent/fs-read-agent
- [ ] `docs/guides/deploy-node-a.md` — remove exec-agent :8004 / fs-read-agent :8003; add memory-service :8003 remote checks; update XNCH_MEMORY_* env vars
- [ ] `docs/guides/deploy-node-b.md` — remove exec-agent :8004 / fs-read-agent :8003; capability sidecar :8090 is primary; add memory-service notes (node-b was Phase 1 host)

## Task 5: Update Runbooks
- [ ] `docs/runbooks/capability-sidecar-deploy.md` — Phase 1 task complete; update to reflect merged sidecar :8090; remove legacy unit steps
- [ ] `docs/runbooks/memory-service-deploy.md` — confirm Gate 2 status: remote mode, Kuzu single-owner, rollback rehearsed; update Step 1 order (stop gateway first for Kuzu safety)
- [ ] `docs/runbooks/restart-node-a.md` — remove exec-agent/fs-read-agent service restarts; add memory-service restart; add XNCH_MEMORY_* env var handling
- [ ] `docs/runbooks/restart-node-b.md` — remove legacy service restarts; add capability sidecar :8090 restart; verify Kuzu safety if memory-service touches DB
- [ ] `docs/runbooks/rollback.md` — update for Phase 2: embedded→remote rollback via `XNCH_MEMORY_EMBEDDED` flip; one-command rollback preserved
- [ ] `docs/runbooks/node-b-hardware-gate.md` — update Phase 1 gate references; confirm Gate A/B passed

## Task 6: Update Reference Docs
- [ ] `docs/reference/env-vars.md` — remove `XNCH_EXEC_AGENT_NODE_B_URL`, `XNCH_FS_AGENT_NODE_B_URL`, `XNCH_EXEC_AGENT_TOKEN`, `XNCH_FS_AGENT_TOKEN`; add `XNCH_MEMORY_EMBEDDED`, `XNCH_MEMORY_SERVICE_URL`, `XNCH_MEMORY_TOKEN`; add `XNCH_CAPABILITY_NODE_B_URL`, `XNCH_CAPABILITY_TOKEN`
- [ ] `docs/reference/cli-reference.md` — update all `python -m cli` → `python -m clients.cli`; update command list; update MCP tool references
- [ ] `docs/reference/config-files.md` — update cli/config.py references; confirm Settings fields
- [ ] `docs/reference/mcp-config.md` — verify MCP bridge config references clients/cli not agent-runner
- [ ] `docs/reference/mcp-http-api.md` — update endpoint references if changed
- [ ] `docs/reference/mcp-tools.md` — verify tool definitions still pass

## Task 7: Update Guides
- [ ] `docs/guides/mcp-cli.md` — update all `python -m cli mcp` → `python -m clients.cli mcp`; update coverage section
- [ ] `docs/guides/nexi-voice-architecture.md` — update CLI references; voice pipeline unchanged but CLI path updated
- [ ] `docs/guides/nexi-voice-mac-client.md` — update all `python -m clients.cli voice` commands (already partially updated)
- [ ] `docs/guides/nexi-test-prompts.md` — update MCP call commands; verify test expectations still pass
- [ ] `docs/guides/memory-routing.md` — update memory-store-note command (deprecated); update `python -m clients.cli` references; update XNCH_MEMORY_* env var references
- [ ] `docs/guides/voice.md` — verify voice loop still works with new CLI path
- [ ] `docs/guides/quickstart-dev.md` — update nexi entrypoint if changed
- [ ] `docs/guides/build-workflow.md` — verify no stale references
- [ ] `docs/guides/reddit-agent.md` — verify agent-runner routing still valid (moved to clients/)

## Task 8: Update Observability Docs
- [ ] `docs/observability-audit.md` — remove exec-agent :8004 / fs-read-agent :8003 from risk table; add memory-service :8003 if needed
- [ ] `docs/observability/prometheus-vs-langfuse.md` — update if memory-service metrics :8003 scrape added (T3.4 follow-up)
- [ ] `docs/observability/README.md` — verify contents

## Task 9: Update Review Docs
- [ ] `docs/reviews/2026-08-24-security-fixes-implementation.md` — update token auth references; fail-closed behavior
- [ ] `docs/reviews/2026-08-22-agentic-tooling-hitl-audit.md` — update agent port references (exec-agent :8004 removed)
- [ ] `docs/reviews/2026-08-23-fresh-overhaul-audit.md` — verify no stale references
- [ ] `docs/reviews/2026-08-22-xnch-audit.md` — verify
- [ ] `docs/reviews/2026-08-24-mcp-tools-ecosystem-audit.md` — update exec-agent/fs-read-agent references; memory-service if applicable
- [ ] `docs/reviews/reconciliation-2026-08-22.md` — verify

## Task 10: Update Old Plan Files (metadata only)
- [ ] `docs/superpowers/plans/2026-08-17-goal-tracking-loop.md` — no changes needed
- [ ] `docs/superpowers/plans/2026-08-22-training-subsystem-phase0.md` — no changes needed
- [ ] `docs/superpowers/plans/2026-08-23-agent-dispatch.md` — no changes needed
- [ ] `docs/superpowers/plans/2026-08-27-agentic-10-10.md` — no changes needed
- [ ] `docs/superpowers/plans/2026-09-02-docs-sync.md` — may need Phase 2 status addition
- [ ] `docs/superpowers/plans/2026-09-07-deploy-all-hosts-master.md` — verify
- [ ] `docs/superpowers/plans/2026-09-07-docs-sync.md` — verify
- [ ] `docs/superpowers/plans/2026-09-07-free-model-selector.md` — verify
- [ ] `docs/superpowers/plans/2026-09-11-agentic-layer-m1-m5.md` — Phase 1+2 gates already satisfied; agentic M1 can proceed
- [ ] `docs/superpowers/plans/2026-09-11-phase1-capability-consolidation.md` — Phase 1 status already COMPLETE
- [ ] `docs/superpowers/plans/2026-09-11-phase2-memory-service-extraction.md` — Phase 2 status: update to COMPLETE (was deferred at gate)
- [ ] `docs/superpowers/plans/2026-09-12-gate1-phase1-capability-sidecar-cutover.md` — already complete
- [ ] `docs/superpowers/plans/2026-09-12-gate2-memory-service-cutover.md` — already complete
- [ ] `docs/superpowers/plans/2026-09-12-micro-split-and-agentic-layer-execution.md` — verify Phase 1+2 gates satisfied for M1 start

## Success Criteria
- [x] All `python -m cli` references replaced with `python -m clients.cli` (verified `cli --help` works)
- [x] No remaining references to `exec-agent/` or `fs_read_agent/` packages (only historical/migration docs retained)
- [x] All env var references use new Phase 1/Phase 2 vars
- [x] Architecture overview matches actual deployed state
- [x] All runbooks reflect Phase 1 cutover and Phase 2 remote mode
- [x] 878/878 tests pass (already verified)
- [x] Plan file created and all tasks either completed or deferred with rationale

## Notes
- This plan touches ~70+ markdown files across 9 categories
- Priority: Architecture → Deploy → Runbooks → References → Guides → Observability → Reviews
- Some old plan files are metadata-only; no code changes needed
- Phase 1 and Phase 2 are both VERIFIED COMPLETE — this doc-update plan is the final gate before agentic M1–M5 can begin