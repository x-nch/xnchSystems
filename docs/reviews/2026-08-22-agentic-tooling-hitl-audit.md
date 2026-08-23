# Agentic Tooling & HITL Security Audit

**Date:** 2026-08-22 · **Scope:** orchestration paths, tool/MCP gating, HITL model, competitor claims
**Headline for interview prep:** the two-path story is stale. One path exists today; its PolicyFilter usage is genuinely unified; the beeAI PoC was deleted on Aug 17 and never shared the class anyway.

---

## 0. PolicyFilter unification — THE load-bearing fact

### As the code stands today: UNIFIED (single implementation, single enforcement point)

One canonical `PolicyFilter` exists in the entire repo:

| Consumer | Import site | Class resolved |
|---|---|---|
| nexi pipeline (engine) | `nexi/main.py:24` via re-export `nexi/pipeline/__init__.py:4`; direct import `nexi/pipeline/run.py:15` | `nexi/pipeline/policy_filter.py:12` |
| LangGraph pipeline (HITL graph) | `xnch/agents/pipeline_graph.py:100` (`from nexi.pipeline.policy_filter import PolicyFilter`, instantiated :104–105 inside the `filter_policy` node) | **same class object** |

Ultimate enforcement is server-side and singular: `PolicyFilter.filter()` → `XnchClient.check_policies_parallel` (`nexi/adapters/xnch_client.py:89`) → xnch policy engine (`xnch/policy/engine.py`, POST `/policy/check`). There is no second filter implementation anywhere (`grep "class.*Policy"` confirms).

### But the claim as framed is FALSE — there are not two orchestration paths

- The beeAI/AgentStack PoC was **removed** from the xnch submodule in commit `9b4f1c0` ("feat(model): route xnch to ornith, drop beeAI + qwenVL routes", Aug 17 2026): −1097 lines, including all of `agents/beeai/*` (8 files), the router mount, config block, and tests. `XNCH_BEEAI_ENABLED` has **zero references in code**; `beeai-framework` is gone from pyproject/uv.lock.
- The handoff doc `misc/opencode/beeai-handoff.md` ("COMPLETE and verified") is **stale** — it describes pre-removal state.
- Worse for the narrative: **even when it existed, beeAI did NOT import `PolicyFilter`.** Recovered from git history (`git show 9b4f1c0^:agents/beeai/policies.py`): it used a separate framework-native layer — `PolicyGateRequirement` + `AskPermissionRequirement` over a local `default_policy_checker()` keyed on `MUTATING_TOOLS = {xnch_memory_store_note, xnch_exec_run}` with an `X-BeeAI-Approval: allow` header. Same philosophy, different code. "Both paths import the same PolicyFilter" was never literally true.

**Interview guidance:** do not say "two paths, one PolicyFilter." Say instead: *"We built a second orchestration PoC, proved deterministic gating works framework-independently against the same tool registry, then deleted it to keep one auditable enforcement path. Every agent capability today flows through one PolicyFilter into one policy engine."* That story survives a live code walkthrough; the current framing does not. History is recoverable if asked: commits `40d8dc4`, `bcd5661`, removal in `9b4f1c0`.

---

## 1. Tool / MCP inventory and interrupt-gate analysis

### Registry model
All product tools register in `xnch_mcp/registry.py`. **Every** `invoke_tool` call enforces role+tier (`registry.py:91–94`) — no bypass path through list/invoke. Trust ladder (`xnch_mcp/auth.py:9–15`): `UNTRUSTED`/`EXTERNAL_AGENT` → T0 read · `TRUSTED_AGENT` → T1 write · `OWNER`/`SYSTEM` → T2 exec.

### Complete tool surface

| Tier | Tools |
|---|---|
| T0_READ | `xnch_fs_list/read/stat/exists/glob`, `xnch_memory_recall/surface`, `xnch_scraper_crawl/batch/social/query`, `xnch_health`, `xnch_status`, `xnch_web_search` |
| T1_WRITE | `xnch_memory_store_note`, `xnch_scraper_store/delete` |
| T2_EXEC | `xnch_exec_run` (actors: nexi/operator/admin/opencode), `xnch_session_run` |
| dynamic | MCP bridge pool tools (`xnch_mcp/bridge/pool.py`) — each external server declares tier+actors in YAML; same enforcement fn (`pool.py:202–204`) |

Dev-tooling surfaces (console scripts, not product-critical): `exec-agent`, `fs-read-agent`, `docs-test-mcp` — share the exec/fs policy files per `infra/no-k3s/shared/exec-policy.yaml:1`.

### Does anything destructive bypass the interrupt gate?

**No — because nothing destructive executes at all.**
- The LangGraph HITL interrupt is real and correctly wired: `pipeline_graph.py:196–208` interrupts every EXECUTION-intent selection by default (`hitl.py:63–84`, mode `"always"`, `xnch/config.py:131`); resume requires typed approve/reject (`routes/pipeline.py:23–32`). Test `test_hitl_mode_never_skips_interrupt` guards the invariant.
- But the graph's `dispatch` node is a **stub** (`pipeline_graph.py:236–240` — emits an event only), and `/execution/execute` is a **simulation stub** (`routes/execution.py:48–68`, deterministic hash outcome). No real-world side effects exist downstream of the gate.
- The only real side-effect surface is `xnch_exec_run`, which does **not** pass through the HITL interrupt but is confined by `ExecPolicy` (`xnch_mcp/exec/policy.py:29–63`): per-host prefix allowlist (status/log/read-only ops only — `infra/no-k3s/shared/exec-policy.yaml:49–173`), denied substrings killing shell metacharacters and all destructive verbs (`;`, `|`, `&`, `` ` ``, `$(`, `sudo`, `rm`, `kubectl apply/delete/patch`, `terraform apply/destroy`, `systemctl start/stop`, `docker run/exec`, …), cwd locked under `/home/x-nch`, 60 s timeout, full audit (`EXEC_RUN` events).
- `xnch_session_run` (T2) funnels into the governed `/session/init` pipeline — i.e., back through policy/HITL wiring, not around it.

**Residual risks worth a sentence if pressed (not blockers):**
1. Allowlisted `pytest` = arbitrary-code-execution vector if a malicious test file lands in the repo.
2. Broad `curl -s` prefix can GET internal endpoints; safe today, fragile if a GET endpoint ever mutates state.
3. With `XNCH_LANGGRAPH_PIPELINE=false` (**default**, `config.py:130`, asserted in `test_hitl.py:67`) the interrupt-bearing router isn't mounted — the flagship demo requires an explicit opt-in flag. Fine as posture; be ready to explain it.

---

## 2. XNCH_BEEAI_ENABLED status

**Flag no longer exists.** Not "defaults false and gates lazily" — the entire path was deleted (`9b4f1c0`: `config.py −8`, `main.py −6`, tests −209). Zero code references outside `misc/opencode/beeai-handoff.md`. Any talking point that says "the flag defaults off" is factually wrong against HEAD. Update the narrative per §0 or resurrect the branch explicitly.

---

## 3. LangSmith / NaraRouter sweep

**NaraRouter: CLEAN.** Zero references repo-wide (code, configs, docs, misc). Due-diligence concern is moot in-tree.

**LangSmith: no active dependency, one latent vector.**
- No first-party code imports langchain/langsmith anywhere.
- `langsmith` appears in `uv.lock` (~line 1065) only as a transitive dep of `langchain-core`, which itself comes from declared root dependency `langchain-openai>=1.4.1` (`pyproject.toml:10`) — **which nothing imports. Vestigial.**
- Latent risk: `langchain-core` auto-enables LangSmith cloud tracing if `LANGSMITH_API_KEY`/`LANGCHAIN_TRACING_V2` env vars are ever present. No such vars exist in any infra/config file today.
- **Recommendation:** delete `langchain-openai` from root pyproject.toml. It buys nothing and keeps an auto-phoning-home library in the venv — exactly the class of thing the interview claims you don't do.

**Adjacent finding (disclosure-ready):** Langfuse *is* integrated for LLM-call tracing (`xnch/observability/langfuse_client.py`, used by `routes/verdict.py`, `nexi/adapters/model_adapter.py`); self-hosted in `infra/no-k3s/node-a/docker-compose.yml`; client hard-no-ops without keys (`langfuse_client.py:46–47`). Caveat: default host is `https://cloud.langfuse.com` (`config.py:79`) — setting keys without overriding host would ship prompt/response traces to a third-party cloud. Recommend defaulting the host to the self-hosted URL. This is observability egress, not inference routing — consistent with your LangSmith rationale, but know the distinction before an interviewer finds it.

---

## 4. Apex / Reznikov Engineering — differentiator still holds (as of 2026-08-22)

- Live page `reznikov-engineering.com/apex`: "**Autonomous** AI Chief of Staff," 18 specialist agents (Chief of staff, Memory, Strategist, Researcher, Finance, Editor, Sales, Marketing, Ops, Social, Engineering, Design, Developer, Analytics, CRM, Calendar, Email, Drive), orb-and-node UI ("TAP THE CORE · CLICK AN AGENT"). Full reveal: "coming soon."
- Active development confirmed on socials: June–Aug 2026 posts; newest (~17h ago) touts a "**Loops engine**" milestone and an autonomous RESEARCHER agent sweeping the web.
- **Zero mention of human approval gates, HITL, confirmation flows, or policy enforcement anywhere on their public surface.** Closest item is "Editor — Quality gate," which reads as an LLM quality check, not a human gate. Their positioning remains autonomy-forward ("plans, executes and follows through — around the clock").
- **Verdict:** the "no visible approval gates" contrast is still accurate. Caveat: evidence is marketing-only and the product hasn't shipped publicly — the claim is currently unfalsifiable rather than proven. Re-check at their "full reveal."

---

## Action items (priority order)

1. [ ] **Rewrite the interview narrative**: one path, one PolicyFilter, one policy engine; beeAI PoC built → verified → deliberately removed (commits above). Kill "two paths share PolicyFilter."
2. [ ] Delete unused `langchain-openai` from root `pyproject.toml` (removes transitive `langsmith`).
3. [ ] Default `langfuse_host` to the self-hosted URL; treat cloud default as footgun.
4. [ ] Archive/annotate `misc/opencode/beeai-handoff.md` as historical (pre-deletion) to avoid future confusion.
5. [ ] Pen-test `ExecPolicy` edge cases (`pytest` vector, `curl -s` GET-mutation, prefix-match bypasses).
