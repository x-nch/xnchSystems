# OpenCode (sst/opencode → anomalyco/opencode) Safety Research
**Date:** 2026-08-24 | **Scope:** permission/safety controls, releases mid-2025→Aug 2026, unattended/CLI behavior
**Method:** 4 web searches + official docs fetches. Current stable: v1.18.18 (2026-08-13). Repo now `github.com/anomalyco/opencode` (docs footer "© Anomaly"); Releasebot still labels it "opencode by SST" — org transfer confirmed by all current doc/release URLs.

## Q1: Current permission/safety controls

- **`permission` block in opencode.json**, values `allow`/`ask`/`deny`, keyed per tool: `read, edit, glob, grep, bash, task, skill, lsp, question, webfetch, websearch`, plus guards `external_directory` (paths outside project) and `doom_loop` (same tool call ×3). Granular object syntax w/ wildcards (`"bash": {"*":"ask","git *":"allow","rm *":"deny"}`), **last matching rule wins**. `permission:"allow"` sets everything. Per-agent overrides merge over global; agents also definable in Markdown frontmatter. https://opencode.ai/docs/permissions (updated 2026-08-21)
- **Defaults are PERMISSIVE**: most tools `allow`; only `doom_loop`+`external_directory` default to `ask`; `.env` reads denied by default. ⚠️ For an unattended Mac runner this means default config = full host access.
- **Agents/modes**: built-in `build` (full access) / `plan` / `general` / `explore`; `--agent <name>` works on both TUI and `run`. Custom agent via `opencode agent create --permissions ...` — anything omitted is denied.
- **No-TTY bypass flag**: the documented equivalent of Claude Code's `--dangerously-skip-permissions` is **`--auto`**: auto-approves every request not explicitly denied; explicit `deny` still enforced. Works on TUI and `opencode run --auto`. Docs list NO `--yolo`/`--dangerously-skip-permissions`. Env override exists separately: **`OPENCODE_PERMISSION`** (inline JSON permissions config). https://opencode.ai/docs/cli (updated 2026-08-23)
- ⚠️ **CONFLICT on a YOLO flag**: GH issues #8463/#9070 (Jan 2026, closed "completed") claim PR #9073 shipped `--dangerously-skip-permissions`/`--yolo` + `OPENCODE_YOLO` env + `"yolo":true` config. But current CLI docs (Aug 23, 2026) don't document it, and a July 5 2026 third-party guide states definitively no such flag exists. Treat as **not shipped in official builds**; verify with `opencode run --help` on your pinned version before relying either way.
- **Headless (`opencode run`) no-TTY behavior — LOAD-BEARING, AMBIGUOUS**: docs do NOT define behavior when `ask` fires headless. Open bug #36762 (2026-07-13, verified on v1.17.18): any permission resolving to `ask` **hangs forever** — no prompt, no timeout, process looks alive, only signature is `message=asking` in `--print-logs`. Requested fail-fast-to-deny NOT implemented. Earlier #13851 (v1.1.60): sessions bootstrap with `question`/`plan_enter`/`plan_exit` = deny; agent-level bash maps were ignored (bug), causing silent cancels.
- Other controls: `serve`/`web` HTTP basic auth via `OPENCODE_SERVER_PASSWORD` (⚠️ no password unless set); global flag `--pure` (no external plugins); experimental `policies` (below).

## Q2: 2025–2026 changes relevant to safety

- **Legacy `tools` boolean config deprecated as of v1.1.1**, merged into `permission` (back-compat kept). Old early-2025 configs using `"tools": {...}` may silently behave differently. (permissions docs)
- **New permission classes added over time** (`doom_loop`, `external_directory`, `skill`, `websearch`, `task`, `question`) — pre-existing configs don't cover them; `external_directory`'s `ask` default is the top headless-hang cause (#36762 path 1).
- **Experimental Policies** (`experimental.policies`, docs updated 2026-08-23): allow/deny `provider.use` per LLM provider, wildcard matching, global overrides project (repo can't re-enable denied provider). Replaces `disabled_providers`/`enabled_providers`. Separate axis from permissions. https://opencode.ai/docs/policies
- **No built-in OS/container sandbox** (HarnessMatch audit, checked 2026-07-30): shell/plugins/MCP inherit user privileges; permissions are app policy, not isolation. Ecosystem fills gap:
  - `opencode-sandbox` npm plugin v0.5.1 (~2026-08-13): wraps every bash call with `@anthropic-ai/sandbox-runtime` — macOS **Seatbelt/sandbox-exec** (relevant to your Mac runner), Linux bubblewrap; write-scoped to project+/tmp; deny-read ~/.ssh, ~/.aws, etc.; default-deny network allowlist; config stored OUTSIDE project to resist prompt injection. https://github.com/isanchez31/opencode-sandbox-plugin
  - comsysto/opencode-sandbox (May 2026): Docker + Squid whitelist + iptables default-deny egress. Official Docker sandbox guides exist (docs.docker.com/ai/sandboxes/agents/opencode).
- **Credential handling/redaction**: built-in = `.env` read denial + `opencode export --sanitize` (redacts transcripts/files). Native API-level redaction hooks requested (#19425, Mar 2026) → **closed not-planned/duplicate Apr 2026**; community plugins cover it (opencode-redactor, opencode-secret-redactor, opencode-secret-tools).
- **MCP client support matured**: `opencode mcp add/list/auth/logout/debug` incl. OAuth flows; MCP tools permissionable via wildcard (`{"mymcp_*":"ask"}`). https://opencode.ai/docs/tools/
- **Hooks/plugins for approval workflows**: plugin events incl. `tool.execute.before/after` (what sandbox plugin uses); `experimental.hook.file_edited/session_completed`; `permission.asked` event surfaced to ACP clients (client can answer allow/deny programmatically).
- Version cadence: ~weekly 1.x releases through v1.18.18 (2026-08-13); release notes reference "v2 servers" and v2.opencode.ai exists — a v2 architecture is emerging.

## Q3: Documented best practice for unattended/CI

- Project's own CI path = **GitHub agent**: `opencode github install` sets up GitHub Actions workflow; `opencode github run` executes there. https://opencode.ai/docs/cli
- Community/operator consensus (py-opencode-wrapper README, verified Jul 15 2026; agents.cli course; HarnessMatch): for headless automation use **explicit `allow`/`deny` rules, never rely on `ask`**; pin a restricted custom agent (`--agent`) whose frontmatter denies what you didn't allow; scope via `permission` + `external_directory` deny; put network/fs isolation OUTSIDE opencode (Docker/Seatbelt/bubblewrap) since none is built in; set `OPENCODE_SERVER_PASSWORD` if exposing serve/web; prefer dedicated low-privilege user/container — nothing in official docs prescribes one.
- No project-published hardening guide found (gap). Enterprise docs page exists (/docs/enterprise/) but wasn't fetched.

## Q4: Silent-behavior risks vs an early-mid-2025 integration

1. **`tools`→`permission` migration (v1.1.1)**: old boolean tool config deprecated; semantics differ (allow/deny vs enable/disable).
2. **`ask` now hangs headless instead of failing** (#36762, open as of Aug 2026) — an integration that once errored out may now deadlock silently; add timeouts + watch for `message=asking`.
3. **Bootstrap denies `question`/`plan_enter`/`plan_exit` in non-interactive sessions** (#13851) and past bugs where agent-level bash patterns weren't enforced — permission merging has been buggy across 1.x.
4. **Repo/org moved** sst/opencode → anomalyco/opencode; update pins/webhooks. Possible TS→Go rewrite implied by Go paths cited in issue #19425 (medium confidence, unverified directly).
5. **`disabled_providers`/`enabled_providers` → policies** replacement.
6. **Flag surface changed**: `--auto` is the sanctioned autonomy switch; `--yolo` claims exist but aren't in docs — never assume parity with Claude Code flags.

## Gaps
- Exact version where `--auto` was introduced: not pinned by sources (post-1.x era; verify against changelog).
- Whether YOLO PR #9073 merged into any release: unresolved conflict (docs say no).
- Enterprise/policies GA status: policies marked experimental.

## Key sources
- https://opencode.ai/docs/permissions · /docs/cli · /docs/policies · /docs/tools/ (all updated ≤2026-08-23)
- https://github.com/anomalyco/opencode/issues/36762 (headless ask hang, 2026-07-13, open) · /13851 (non-interactive pipeline, 2026-02-16) · /19425 (redaction hooks, closed 2026-04) · /8463 & /9070 (YOLO proposals, Jan 2026)
- https://releasebot.io/updates/sst/opencode (v1.18.x feed, Aug 2026) · https://www.codeagentswarm.com/en/guides/opencode-yolo-mode (2026-07-05) · https://harnessmatch.dev/harnesses/opencode (checked 2026-07-30) · https://npm.io/package/opencode-sandbox (v0.5.1, 2026-08-13) · https://github.com/comsysto/opencode-sandbox (2026-05) · https://docs.docker.com/ai/sandboxes/agents/opencode · https://pypi.org/project/py-opencode-wrapper (2026-07-15)
