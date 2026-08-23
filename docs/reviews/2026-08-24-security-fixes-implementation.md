# Security Fixes Implementation Log — 2026-08-24

Companion to `2026-08-24-mcp-tools-ecosystem-audit.md`. All F/U-series items
were approved for implementation this session. TDD throughout; every changed
surface has failing-test-first coverage.

## ✅ LIVE NOW (Mac-side P0 — active before the next cron fire)

| Item | Change | Verified by |
|---|---|---|
| F1 model pin | Global `~/.config/opencode/opencode.json`: custom provider `xnch-litellm` → LiteLLM proxy `192.168.1.10:4000/v1`, model `ornith` with explicit `limit {context:32768, output:8192}` | live smoke run routed via litellm (`model=ornith` in provider error pre-fix, SMOKE-OK post-fix) |
| F1 scoped firewall | Runner writes per-workspace project config: `experimental.policies` deny `*` / allow `xnch-litellm` | unit `test_handle_once_writes_workspace_provider_policy` |
| F2 restricted agent | `~/.config/opencode/agents/xnch-dispatch.md`: bash/task/lsp/skill/question/external_directory/doom_loop DENY, all 7 personal MCP servers denied by wildcard, webfetch/websearch/edit allowed, model pinned `xnch-litellm/ornith`, steps≤40 | live probe: bash refused ("shell access is disabled"), workaround stayed inside allowed tools/workspace |
| F3 env allowlist | runner `_spawn_env()` — child gets PATH/HOME/USER/LOGNAME/TMPDIR/SHELL/LANG (+defaults) only; `XNCH_GATEWAY_SECRET` et al. can no longer reach agent processes | units incl. secret-drop test |
| F3 scope guard | `from_env()` refuses to start unless command pins `--agent` (escape hatch `XNCH_ALLOW_UNSCOPED_AGENT=1`) | unit `test_config_rejects_unscoped_agent_command` |
| deploy | Live plist updated (`run --agent xnch-dispatch`, guard flag), hardened runner mirrored to `/Users/xnch/xnchSystems/agent-runner` (the checkout launchd actually runs), service unloaded/reloaded — PID up, polling | `launchctl list`, boot log line |
| U3 sandbox (scoped) | `opencode-sandbox` plugin loaded **per-workspace only** via project config + strict inline `OPENCODE_SANDBOX_CONFIG` (deny-read ~/.ssh etc., default-deny network). Interactive sessions unaffected. Plugin is fail-open by design → defense-in-depth beneath the bash deny | unit `test_handle_once_scopes_sandbox_plugin_to_workspace` |

## ✅ IN-TREE (implemented + tested here; needs commit/push/deploy)

| Item | Files |
|---|---|
| F4 fail-closed tokens | `exec_agent/server.py`, `fs_read_agent/server.py`: unset token ⇒ 503 loud misconfig; wrong/missing ⇒ 401 constant-time compare | `tests/test_agent_servers_auth.py` (6) |
| F6 addendum on deployed design | Re-based onto upstream `1a3ecbe` (which already shipped keyword-allowlist→elevation + in-flight guard + retry): added `ELEVATED_KINDS` force-elevation — plan entries declaring kind∈{send_email, submit_application, purchase, publish, exec, external_action, delete} or `risk:"elevated"` are NEVER filed low-risk, even when keywords match | `xnch/jobs/goal_dispatch.py`, `xnch/tests/test_agent_goal_dispatch.py` (14 ✓ incl. upstream's) |
| F7 direct-dispatch kill-switch | `POST /agents/dispatch` now 403 unless `XNCH_AGENTS_DIRECT_DISPATCH_ENABLED=true` (deny-by-default); enabled path logs a warning (approval-bypass audit marker) | `xnch/routes/agents.py`, `xnch/config.py`, `xnch/tests/test_agent_routes.py` (7 ✓) |
| F8 gateway defaults | `opencode_auto_approve=False`; `_verify_api_key` fails closed (503 when unset); `child_env()` allowlist passed to both spawn paths | gateway suite (10 ✓) |
| A15 hygiene | `langchain-openai` removed from root pyproject; uv.lock re-synced | lock diff |
| U1 secret scanning | gitleaks 8.30.1 + trufflehog 3.97.0 installed (brew); `scripts/security/hooks/pre-commit` (staged-scan, redacted, blocks on finding); wired via core.hooksPath in parent + both submodules | hook script; initial scans clean |

Initial scan results: **0 findings in full repo git history** (gitleaks);
trufflehog `--only-verified` clean. Note: the agentmemory shared-secret in
global opencode config is a low-entropy string no scanner pattern matches —
see follow-ups.

Full sweep at session end: **59/59** root+xnch affected suites, **10/10** gateway.

## 🔎 Session discoveries (material to prior assumptions)

1. **Deployed gate7 xnch is NEWER than the parent-repo submodule pin**: runs
   `1a3ecbe` ("audit continuity + allowlist elevation + in-flight guard") vs
   pinned `e59c5ee`. The step-kind allowlist I reported as "never implemented"
   WAS implemented on that branch — as keyword-allowlist→elevation (unmatched
   ⇒ elevated, still human-gated) rather than refusal. My local work was
   rebased onto it; nothing was duplicated or overwritten. **Parent pin bump
   is pending** (needs a commit in the parent repo):
   `git add xnch && git commit -m "chore: bump xnch ptr (goal-dispatch hardening)"`.
2. Live cron fires at **minute 3**, not 30 (`XNCH_GOAL_DISPATCH_CRON_MINUTE=3`
   override on gate7).
3. gate7 env already sets `XNCH_GOAL_DISPATCH_ENABLED=true`,
   `XNCH_EXEC_AGENT_TOKEN`, `XNCH_FS_AGENT_TOKEN` (node-a side),
   `XNCH_BEEAI_*` flags (feature-flag present; PoC remains off-path).

## 📋 STAGED (remote/supervised — prepared, not executed)

1. **F5a vLLM auth**: node-b was unreachable (GPU node asleep). Steps:
   add `--api-key <new-secret>` to the vLLM serve args on node-b, set matching
   `api_key:` in `infra/no-k3s/node-a/litellm-config/config.yaml`, restart both;
   then verify from Mac: `curl -H "Authorization: Bearer …" http://…:8082/v1/models`.
2. **F5b nexi auth sweep**: mount remaining bare routers with token dependency
   (nexi holds no JWT path by design; Hybrid-B token middleware is the fit) or
   firewall 8000 to node-a only. Requires nexi submodule change + pointer bumps.
3. **node-b sidecar token check**: confirm exec/fs systemd units on node-b set
   the same `XNCH_{EXEC,FS}_AGENT_TOKEN` values as gate7 — required before
   restarting them once fail-closed code deploys (they will refuse otherwise,
   loudly, by design).
4. **F7 deployment note**: after next xnch deploy, muse's manual dispatch form
   will 403 until `XNCH_AGENTS_DIRECT_DISPATCH_ENABLED=true` is added to
   gate7's `/home/x-nch/.xnch/xnch.env` (deliberate friction — decide, then set).
5. **U2 completion**: mcp-scan is now Snyk-gated; `scripts/security/scan-mcp.sh`
   is ready — set `SNYK_TOKEN` to activate scheduled scans.

## 📌 Open follow-ups
- Rotate the agentmemory shared secret currently sitting plaintext in global
  opencode config (requires service-side change on node-a; headless exposure
  already mitigated by F2 tool-denies).
- U4: dedicated low-privilege macOS user for the launchd runner (documented
  option; OS-level change left to operator).
- Consider building the code-review-graph for this repo root (graph absent;
  next review cycle would benefit).
