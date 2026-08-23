# MCP / Skills / Tools Ecosystem Audit + Upgrade Plan — 2026-08-24

Scope: standing orchestration path (xnch/nexi pipeline) **and** the live goal-driven
auto-dispatch path (cron → approval → Mac runner → opencode). External research in
`research_mcp_ecosystem_2026-08/` (3 sourced findings files, researched 2026-08-24).
Nothing from Part 3 has been implemented; every item below awaits explicit go-ahead.

---

## ⚡ THE LOAD-BEARING ANSWER: PolicyFilter coverage of auto-dispatch

**Question: does a dispatched opencode run go through the same PolicyFilter/HITL gate
as the primary orchestration path?**

**Answer: NO — the auto-dispatch path is a parallel surface with no PolicyFilter at all.
It has exactly one governance point: a single human approval click per step.**

Code-level chain, fully verified:

1. `xnch/main.py:188-200` — APScheduler job `goal_dispatch` (hourly, `minute=30`,
   enabled by `XNCH_GOAL_DISPATCH_ENABLED`, pinned to goal `2c821d69…` via config)
   calls `run_due_dispatch`.
2. `xnch/jobs/goal_dispatch.py:57-97` — claims due goal, builds the prompt directly
   from `simulation_plan[steps_completed]` via `build_step_prompt()`, files a
   `goal_step` APPROVAL. **The prompt never passes through the nexi pipeline**
   (`intent_interpreter → generate_options → PolicyFilter → Evaluator → select_decision`).
   No policy evaluation of any kind occurs.
3. Human approves in muse (`/approvals/{id}/decide`, gateway-token gated — that auth
   IS enforced, verified `xnch/routes/workflows.py:289`) → approve-side hook
   `spawn_agent_run_for_approval()` queues an `agent_run`.
4. Mac runner (`agent-runner/xnch_agent_runner/runner.py:95-145`) claims it via
   `/agents/dispatch/next` (HMAC token, verified), spawns bare
   `opencode run -- <prompt>` in a fresh `~/xnch-agents/<run_id>/` workspace.
5. From that click onward the opencode process is completely ungoverned by xnch:
   no per-action interrupts, no ExecPolicy, no fs-policy, no tool gating. The v0 spec
   says this explicitly: *"Human click = the approval … v0 does not wrap agent internals"*
   (`docs/superpowers/specs/2026-08-23-agent-dispatch-design.md:25-27`). Scheduled
   auto-dispatch was listed as a v0 **non-goal** (line 36) — v1 added it on top.

This is the same shape as reconciliation finding A6 (2026-08-22): "bypasses HITL when
it runs." The approval click is real and tested (`xnch/tests/test_agent_goal_dispatch.py`
covers gate→spawn→outcome→back-pressure end-to-end), but it is *pre-approval of an
opaque prompt*, not enforcement *inside* the run. Everything below compounds this.

### Compounding findings on the same path (all code-verified today)

| # | Finding | Evidence |
|---|---|---|
| C1 | **Silent external inference.** Dispatched runs get no model override (runner passes no `-m`; global opencode config has no `model` key). Empirically, opencode's history is dominated by providerID `opencode` (`big-pickle`, `x-preview-f-free`) = OpenCode Zen hosted gateway. Unattended runs are routing inference to an external service by default — violates the standing LiteLLM-only constraint reasserted this session. | opencode.db stats: 7,558× `opencode/big-pickle`; plist + runner pass no model |
| C2 | **Permissive tool defaults inside runs.** Global `~/.config/opencode/opencode.json` has NO `permission` block. OpenCode defaults are allow for bash/edit/etc.; headless `ask` hangs forever (open bug #36762, confirmed on pinned v1.18.21 which does ship `--auto`: "auto-approve permissions that are not explicitly denied (dangerous!)"). | global config keys = `$schema, mcp, plugin` only |
| C3 | **Seven MCP servers auto-load into every unattended run**, including remote endpoints (vercel, Google Analytics via stape, firecrawl) — network-egress tools far beyond what "shortlist companies / write deliverable.md" steps need. Classic over-broad-scope confused-deputy surface (Part 1 research §4). | global config `mcp` block |
| C4 | **Full env inheritance into the agent process.** Runner `subprocess.run(...)` passes no `env=`; the launchd service env (incl. `XNCH_GATEWAY_SECRET`) flows into opencode and anything it spawns. This is precisely the never-fixed half of A3/core-F1 ("credential re-scoping"). | runner.py:114-120; plist env vars |
| C5 | **No step-kind allowlist exists anywhere.** The design decision ("allowlist of low-risk step kinds") was recorded but never implemented as a hard check: `run_due_dispatch` files an approval for ANY plan entry, unclassified; `create_goal_approval` payload carries no risk_class. Decision ≠ code. | goal_dispatch.py:36-97 (whole file); grep repo-wide |
| C6 | **Direct dispatch bypasses the gate entirely.** `POST /agents/dispatch` queues ANY prompt from ANY gateway-token holder with no approval linkage (approval_id is optional). The HITL gate only covers cron-filed goal steps. | xnch/routes/agents.py:30-35 |
| C7 | **agent-gateway A3 fix never landed.** `opencode_auto_approve: bool = True` default still appends `--auto`; subprocess spawn still inherits full env; `_verify_api_key` still fails open when unset. Currently not referenced by any deploy artifact (port 8100 unreferenced) — latent footgun, not live exposure. | scripts/agent-gateway/config.py:28, adapters/opencode.py:20-21, base.py:63-68, main.py:39-41 |

---

## 🔴 Must-fix BEFORE next unattended cron fire

The cron fires hourly (minute 30). C1/C2/C3/C4 mean each fire currently executes an
externally-routed, permissively-tooled, credential-carrying agent run behind one click.
Ranked order:

1. **Kill silent external routing (C1).** Pin the model for headless runs — set `model`
   in global opencode config to the local vLLM/LiteLLM provider entry (e.g.
   `vllm-quality/qwen-quality` already configured), or make LiteLLM→Claude an explicit
   opt-in per the standing constraint. Belt-and-suspenders: `experimental.policies`
   deny-by-default on non-local providers (`provider.use`), which project configs
   cannot override.
2. **Scope the dispatched agent (C2+C3).** Create a dedicated restricted opencode agent
   (frontmatter deny-by-default: allow read/glob/grep/edit/webfetch/websearch for the
   job-search step kinds; bash narrowly allowed or denied; `external_directory: deny`;
   deny all seven personal MCP server tools, e.g. `{"vercel_*":"deny", …}` or better,
   move personal MCPs out of global config so headless runs don't see them at all).
   Remember: `ask` values HANG headless (#36762) — use explicit allow/deny only.
   Runner change: `XNCH_AGENT_ARGS="run --agent xnch-dispatch"`.
3. **Env-scoped spawn (C4).** Runner passes an allowlisted env (PATH/HOME/
   PYTHONUNBUFFERED/XNCH_AGENT_*) — never the full service env. Same three-line fix
   class as core-F1, applied where it's actually live.
4. **(Fastest interim option if time-boxed:)** pause the cron
   (`launchctl unload` on the runner or disable the scheduler job) until 1–3 land.
   One click of downtime vs. indefinite exposure.

Items 5–7 are serious but not per-fire exposures; they can follow within days:
5. exec/fs-agent fail-open tokens → require non-empty token at startup, fail closed,
   constant-time compare (`exec_agent/server.py:34-39`, `fs_read_agent/server.py:33`).
6. Remaining A4 surfaces: vLLM :8082 `--api-key` or firewall-to-node-a; nexi router auth sweep.
7. Purge or fix scripts/agent-gateway defaults (A3 proper).

---

## Part 1 — External research summary (details + URLs in research_mcp_ecosystem_2026-08/)

**MCP protocol** (`findings_mcp_protocol.md`): latest stable spec is **2026-07-28**
(breaking: stateless protocol, no initialize handshake, MRTR replaces server-initiated
requests, SSE resumability removed; Roots/Sampling/Logging deprecated). Auth now uses
Client ID Metadata Documents (DCR deprecated), mandatory RFC 9207 `iss` validation;
registry is live but preview-grade — namespace verification only, **no package signing
exists**. For us: stdio remains the recommended local transport (we're aligned);
Python SDK v2.0.0 targets 2026-07-28 — pin `<2` until we choose to migrate. No HTTP
transport adoption warranted; nothing here forces action beyond awareness.

**Security patterns** (`findings_mcp_security.md`): tool poisoning is structural
(Invariant Apr 2025; MCPTox >60% success; line-jumping fires at context load, pre-use);
rug pulls formalized as CVE-2025-54136; first in-the-wild malicious MCP server
(postmark-mcp, Sept 2025) plus npm worm planting rogue configs (Feb 2026); Trend Micro:
492 MCP servers exposed with zero auth. CVEs mirror our exact history: CVE-2025-49596 /
CVE-2026-23744 = unauthenticated localhost/0.0.0.0 dev services → RCE. Ranked
mitigations for our shape: loopback+auth everywhere; deny-by-default per-tool
allowlists honoring readOnlyHint/destructiveHint; hash-pin tool definitions; curated +
pinned servers; secret isolation; scan-on-change.

**OpenCode** (`findings_opencode.md`): stable v1.18.x weekly; repo moved
sst→anomalyco. `--auto` is the sanctioned headless bypass (verified present on our
v1.18.21). Headless `ask` hangs forever (#36762 open). Legacy `tools` booleans
deprecated into `permission` (v1.1.1); new permission classes keep appearing, so stale
configs under-cover. No built-in sandbox; ecosystem answer for macOS =
`opencode-sandbox` plugin (Seatbelt, write-scoped project+/tmp, deny-read ~/.ssh/.aws,
default-deny network allowlist). Native redaction hooks rejected upstream; use
`export --sanitize`/community plugins. Confirmed implication for us: our integration
predates several of these shifts and its ambient-config reliance (C2/C3) is exactly the
documented anti-pattern.

## Part 2 — Standing-findings status board (code-verified unless noted)

| Item | Status |
|---|---|
| NaraRouter | ✅ Still unadopted — zero references repo-wide (matches 08-22 sweep). Skepticism stance unchanged. |
| LangSmith | ✅ Still absent as adopted dep; ❌ hygiene: root `pyproject.toml:17` still carries `langchain-openai>=1.4.1` (A15 deletion never done) keeping transitive langsmith latent. |
| Orchestration consolidation | ✅ Single path holds; beeAI/AgentStack absent from active tree. |
| LiteLLM-only inference | ❌ **Violated in practice by default** on dispatched + interactive opencode runs (C1) — mechanism differs from the rejected `-m` flag but lands in the same place: silent external routing. |
| exec/fs-agent unauth LAN finding | 🟡 Partially fixed — `_verify_token` exists on both but **fails open when token env unset** and binds remain 0.0.0.0 (`infra/no-k3s/node-b/systemd/*.service`). Deployed-env token presence unverifiable from this Mac (ssh check needed). |
| nexi/vLLM unauth surfaces | 🔴 No in-tree evidence of fix since A4 (nexi still has no JWT path per 08-23 audit; vLLM `--api-key` absent). Same ssh caveat. |
| HITL approvals route auth | ✅ Fixed — `/approvals/{id}/decide` is gateway-token gated (`workflows.py:289`). |
| Credential re-scoping (core-F1/A3) | 🔴 Never landed — and the live runner reproduces the identical defect (C4); gateway copy also unfixed (C7). |
| Step-kind allowlist decision | 🔴 Recorded, never implemented (C5). |
| Goal auto-dispatch gate | 🟡 Real single-click gate, tested; no intra-run governance (top section). |

## Part 3 — Prioritized plan (fixes above capabilities; nothing implemented yet)

**F-series (fixes — inherit priorities from sections above):**
- F1 (P0, pre-cron): pin local model/provider for headless runs + policies deny external providers (C1).
- F2 (P0, pre-cron): dedicated restricted dispatch agent; strip MCP servers from headless scope (C2/C3).
- F3 (P0, pre-cron): runner env allowlist (C4). ~10 lines in runner.py + tests.
- F4 (P1): fail-closed tokens in exec/fs agents; verify deployed env via ssh (item 5).
- F5 (P1): vLLM api-key/firewall + nexi auth sweep (A4 remainder, item 6).
- F6 (P1): implement the step-kind allowlist for real — classify at approval-filing time
  (`run_due_dispatch`), tag approvals risk_class low/elevated using the existing workflows
  machinery (elevated ⇒ stricter decider), and hard-refuse auto-filing for unclassified kinds (C5).
- F7 (P1): close `/agents/dispatch` direct-write bypass — require approval linkage or restrict to muse proxy (C6).
- F8 (P2): fix/purge agent-gateway defaults (C7); remove `langchain-openai` (A15).

**U-series (upgrades — each needs go-ahead):**
- U1 **gitleaks + trufflehog** (secret scanning — strongly recommended regardless):
  gitleaks as pre-commit across parent + both submodules; trufflehog periodic
  filesystem/docker scan including `~/.config/opencode` and `.env*` (an
  `AGENTMEMORY_SECRET` already sits plaintext in the global opencode config — found
  during this audit). Directly closes the git-committed-credentials recurring class.
  Scope: zero runtime scope; pure CI/local tooling. HITL: n/a (read-only scanning).
- U2 **mcp-scan** against opencode/global MCP configs on change: tool-poisoning +
  rug-pull hash-pinning detection across the 7 loaded servers. Scope: read-only scans.
- U3 **opencode-sandbox plugin (Seatbelt)** on the Mac runner: OS-level write-scope
  (project+/tmp), deny-read ~/.ssh/.aws, default-deny network allowlist. This is the
  missing layer beneath F2 — app permissions without OS isolation remain advisory.
- U4 (optional, post-F-series): dedicated low-privilege macOS user for the launchd
  runner; document in deploy runbook.
- Protocol housekeeping (no action now): stay stdio-only; when touching Python SDK,
  pin `mcp>=1.27,<2`; treat registry listings as unsigned until signing exists.

**Considered and REJECTED (named, with reasons):**
- **LangSmith** — reaffirmed rejected (routes inference externally even self-hosted; 08-22 evaluation stands).
- **NaraRouter** — remains unadopted under due-diligence skepticism; nothing new changes that.
- **Heavy MCP security gateways** (MintMCP, Lasso, Docker MCP Gateway, Pipelock) — wrong size for solo/local-first; U1–U3 cover the actual threat model.
- **Job-board/email/calendar MCP servers for the goal** — broad OAuth scopes (full mailbox class) are the documented over-breach pattern; ToS-risky scraping; firecrawl behind existing HITL covers research needs.
- **Remote MCP servers in unattended scope** (current vercel/GA/firecrawl globals) — kept for interactive work only after F2 separates configs.
- **Raw `-m provider/model` cloud routing** — already rejected standing; C1 shows the default-path variant must be fixed too.

## Verification gaps (needs ssh to node-a/gate7 or operator confirmation)
- `XNCH_GOAL_DISPATCH_ENABLED=true` actually set in deployed xnch env (ground truth says LIVE; consistent with cron+click behavior, but env not inspectable from here).
- `XNCH_EXEC_AGENT_TOKEN` / fs-agent token set in deployed units (fail-open otherwise).
- Whether vLLM/nexi gained firewalling outside the repo.

## Audit-session notes
- `xnch/` submodule was uninitialized in this working tree; initialized and checked out
  at the parent-pinned commit (e59c5ee) purely read-only to audit dispatch code.
- Knowledge-graph MCP had no graph for this repo root (stale default path); audit used
  targeted grep/read instead. Consider building the graph before the next review cycle.
