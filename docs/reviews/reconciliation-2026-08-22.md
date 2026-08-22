# XNCH Systems — Cross-Cutting Reconciliation of 8 Component Reviews (2026-08-22)

**Source docs:** [core] xnch audit · [nexi] persona audit · [mem] memory verification · [opt] Node B inference audit · [tool] agentic tooling & HITL audit · [dep] deployment audit · [ui] interface audit · [obs] observability audit
(Files: `xnchSystems/docs/reviews/2026-08-22-xnch-audit.md`, `xnchSystems/misc/nexi-persona-integrity-audit-2026-08-22.md`, `xnchSystems-ox/misc/memory-subsystem-verification-2026-08-22.md`, `xnchSystems-ox/docs/node-b-inference-audit-2026-08-22.md`, `xnchSystems/docs/reviews/2026-08-22-agentic-tooling-hitl-audit.md`, `xnchSystems/docs/deployment-audit-2026-08-22.md`, `xnchSystems-ox/docs/ui-audit-web-shell.md`, `xnchSystems-ox/docs/observability-audit-2026-08-22.md`)

---

## ⚡ LOAD-BEARING CLAIM — PolicyFilter Verdict

**CONFIRMED DRIFTED.** As code stands today there is exactly **one** orchestration path, and its PolicyFilter usage is genuinely unified (`nexi/pipeline/policy_filter.py:12`; imported by nexi engine at `nexi/main.py:24` and by the LangGraph graph at `xnch/agents/pipeline_graph.py:100`) — but the claim "both paths import the exact same PolicyFilter" is false: the beeAI/AgentStack PoC was deleted Aug 17 (commit `9b4f1c0`), and even when it existed it used its own framework-native gate (`PolicyGateRequirement` + `AskPermissionRequirement`) and never imported PolicyFilter. Per the stated rubric this is the single highest-priority item in the entire reconciliation → A1 below.

---

## Section A — Master Prioritized Action List

Work top-to-bottom without re-reading the source docs.

### BLOCKER

| # | Item | Sources | Fix direction |
|---|------|---------|---------------|
| A1 | **HITL narrative's central fact is stale.** "Two orchestration paths share one PolicyFilter" fails a live code walkthrough: beeAI deleted (`9b4f1c0`), `XNCH_BEEAI_ENABLED` has zero code references, `misc/opencode/beeai-handoff.md` claims "COMPLETE and verified" against a dead tree. (Apex contrast itself still holds per [tool §4], but evidence there is marketing-only.) | [tool §0/§2], [nexi F4] | Adopt the corrected framing from [tool §0]: *"one path, one PolicyFilter, one policy engine; PoC built → verified → deliberately removed."* Annotate the handoff doc as historical. Human decision: resurrect branch or archive fossil. |
| A2 | **Live credentials committed to git.** LiteLLM master key appears in both `infra/k8s/secrets-create.sh` and `infra/openclaw/claude-code-agentmemory.env` (cross-confirming it is real); also postgres password, auth_secret, Langfuse secrets, agentmemory secret. Plus hardcoded PG DSN default in `xnch/config.py:67` (already in git history). `.gitignore` lacks `*.env` pattern. | [dep S1], [core F3], [mem Task3#3] | Rotate all listed credentials; add `*.env` to `.gitignore`; move DSN to env-only with no default; operator decides rotate-only vs history rewrite. |
| A3 | **agent-gateway skip-permissions survived by relocation.** `scripts/agent-gateway/adapters/opencode.py` appends `--auto` with default `opencode_auto_approve=True`; spawned CLIs inherit the full environment (no allowlist); `_verify_api_key` fails open when `api_key=None` (default) → unauthenticated service spawns auto-approving agents carrying every credential. Mitigated only by 127.0.0.1 bind. | [core F1] | Three small diffs: default `opencode_auto_approve=False`; env allowlist passed to `create_subprocess_exec`; fail-closed auth when key unset. |

### HIGH

| # | Item | Sources | Fix direction |
|---|------|---------|---------------|
| A4 | **Unauthenticated surfaces on LAN + bare REST routers.** vLLM :8082 serves unauth on 0.0.0.0 (litellm config key is decorative — no `--api-key`); same for nexi :8000, fs-read :8003, exec-agent :8004 (executes commands — highest-value target). Separately, core routers are mounted without auth: unauth callers can approve/reject HITL interrupts, record execution outcomes, claim goals. Only chat/session check Authorization. | [dep S3], [core F2] | Add `--api-key` to vLLM + auth/firewall the agent ports to Node A; sweep routers with `include_router(..., dependencies=[...])`. |
| A5 | **HITL gate is operationally invisible end-to-end.** Zero audit events/metrics/traces on the most security-critical path; pending gates have no timeout (AsyncPostgresSaver keeps state forever); zero UI representation of approvals/scheduler/goals anywhere in `web/src`; flagship demo path requires explicit opt-in flag (`XNCH_LANGGRAPH_PIPELINE=false` by default). Four reviews converged independently. | [obs TL#3+§2], [ui §2], [core F5], [tool §1 residual] | Add `EventLog.emit` + counters (`hitl_gates_open`, `hitl_decisions_total`, `hitl_gate_age_seconds`) in `routes/pipeline.py`; stale-gate sweeper (>15 min alert); build approval-queue UI surface; decide demo flag posture. |
| A6 | **Goal loop can't run autonomously — and bypasses HITL when it runs.** Nothing calls `claim_next_goal` on a cadence (APScheduler runs learning crons only); goal advancement via `/execution/outcome` never routes through the graph's EXECUTION interrupt; a slowly-but-successfully wrong goal runs to `max_steps` with zero human gates. Contradicts "done" status elsewhere (see C). | [core F4+F5] | One wiring change: scheduler job → claim → run step through pipeline so goals inherit the interrupt; add per-goal approval counter as backstop. |
| A7 | **`xnch_memory_store_note` silently broken for every allowed actor.** Handler passes `session_id=` but `PgEpisodicStore.store_episode` has no such param → TypeError caught into error payload; tests pass because mocks mask it. Curated-note writes have never worked. | [mem NF#1] | Add `session_id` to PG store + schema (also unlocks A17) or drop kwarg at handler; add non-mocked integration test. |
| A8 | **Persona enforcement gaps (adversarial rating 2/10).** Disagreement protocol absent from prompt AND code (0 grep hits; no state mechanism); proactivity cap (5/day) documentation-only — generator never scheduled, delivered events never deleted from Redis (would re-inject every turn until TTL); dry-humor/exemplars never ported; eval harness grades only traits that survived. | [nexi F1-F3] | Ship protocol into `persona.yaml` + Redis objection-flag (`objection:{session}:{topic}`, TTL 24h); INCR daily cap in `queue_event` with midnight expiry; delete-on-surface in `get_pending`; schedule `check_and_queue` or delete engine; port exemplars; add adversarial eval cases. |
| A9 | **No metrics/alerting stack exists at all.** Zero Prometheus/Grafana/Alertmanager/exporters; nothing scrapes vLLM `/metrics`; Redis death invisible (#1 silent-failure risk), langfuse-postgres disk fill rots tracing invisibly, LiteLLM has no nexi fallback, tailscale funnel loss silent; `/health` checks only Redis ping and returns degraded-as-200. | [obs all], [dep G1/G3] | Execute [obs §5] rollout: (1) zero-infra code fixes, (2) Prometheus+Grafana+Alertmanager+node_exporter+cAdvisor, (3) DCGM, (4) Rows 1–4 dashboards + minimal alert set. |
| A10 | **Boot-ordering silent failure across nodes.** Node B units start after `network.target` only; nexi lifespan does no connectivity probes so it reports healthy with Node A down; `Restart=on-failure` never fires; boot scripts' `wait_http` counts degraded as up. | [dep S2/§3], [obs §3] | `ExecStartPre=` readiness curls on node-b units (+ optional `nexi-ready` gate); extend `/health` to probe PG + LiteLLM; fix `wait_http` semantics. |
| A11 | **GPU margin one incident from queueing cliffs, and unverifiable performance claims.** KV pool ≈2–4 GiB vs ~3 GiB per full 32k sequence → second long sequence preempts; briefed mitigations (`--kv-cache-dtype fp8`, offload) were never applied; util 0.95 not 0.92; "~171 tok/s" has no provenance anywhere (folklore); no benchmark baseline exists; GPU metrics unscraped/no DCGM. | [opt §1–3,§6], [obs GPU row] | Run live checklist (opt Appendix A); apply fp8 after Ampere/tool-call smoke test; then raise max-num-seqs; record `vllm bench serve` baselines to git-tracked JSON; scrape :8082/metrics. |
| A12 | **Bi-temporal fact invalidation claimed but never implemented.** Docs assert Graphiti-style validity semantics; Kuzu schema has no temporal columns, no supersede logic; `upsert_relation` overwrites confidence blindly; stale facts coexist with successors at equal standing in recall. | [mem Task2] | Decide implement-vs-descope ([mem close-out #1]); if descope, correct architecture-suite docs. Adding `session_id` column work pairs with A7/A17. |

### MEDIUM

| # | Item | Sources | Fix direction |
|---|------|---------|---------------|
| A13 | Split-brain episodic persistence: legacy SQLite `EpisodicStore` still dual-written alongside PG canonical (verdict.py:133/:142, execution.py:76/:85/:123). Contradicts [dep row 5 "done"]. | [mem Task3#2, NF#4] | Migrate remaining reads/writes to PG; drop second store. |
| A14 | Langfuse capture thin/inert/misdirected: word-count tokens; `tokens_used` misfiled under `maxTokens`; failures swallowed; LLM-call-only spans; chat gateway emits nothing; LiteLLM callback absent; keys unset everywhere (inert) but host defaults to cloud.langfuse.com (egress footgun). | [mem Task4], [obs traces], [tool §3] | Real usage from provider responses; failure counter; trace_id at model_adapter sites; memory-op spans or relabel tier-4 docs; default host to self-hosted URL; enable LiteLLM langfuse callback. |
| A15 | Vestigial `langchain-openai` dep keeps transitive `langsmith` in venv with latent auto-tracing if env vars ever appear. NaraRouter itself: clean. | [tool §3] | Delete from root pyproject.toml. |
| A16 | Workspace/checkout governance: no per-agent worktree isolation (gateway runs all agents in one shared cwd — file collisions); multiple divergent checkouts (`~/xnchSystems`, `-ox`, `-wt`, `-ornith`) with Node B launch provenance untracked. | [core F6], [nexi F4], [opt caveat] | Pin canonical checkout, record git SHA at service start surfaced in `/health`; implement per-agent worktrees before concurrent gateway use. |
| A17 | tier_graph cross-tier "produced" edges can never materialize (`episodes` has no `session_id`); unit test masks it with fake data. | [mem NF#2] | Same schema fix as A7; add honest test data. |
| A18 | Designed L0→L1 promotion is dead code: `flush_to_working_memory` has zero production callers; sensory content reaches working memory only incidentally via voice transcript. | [mem NF#3] | Wire into voice path or delete. |
| A19 | Packaging gap: root project imports modules requiring `redis`, `numpy`, `onnxruntime`, `tokenizers` — none declared. | [mem NF#7] | Declare deps or scope root package honestly. |
| A20 | Zero resource limits (no MemoryMax/CPUQuota/mem_limit/cpus) + unbounded json-file logs → noisy-neighbor and silent disk-fill risk. | [dep S4/G2/G3] | Compose logging max-size/max-file; systemd MemoryMax/CPUQuota for top offenders. |
| A21 | GPU exclusivity enforced only by human discipline: Vision-stack systemd units were never written; mutual `Conflicts=` pattern drafted but unshipped. | [opt §5], [obs GPU] | Write the three mutually-conflicting units incl. StartLimit guards when vision lands. |
| A22 | Model-inventory/routing truth gaps: LiteLLM routes only ornith:8082 — nothing can reach vision slot 8083 even if Qwen2.5-VL runs; llama.cpp :8081 has zero repo references (hand-managed on the node or gone); GLM-4.7-Flash@8083 conflated from another machine — 8083 is the reserved Qwen-VL slot; `opencode.jsonc` qwen-vl provider points at stale subnet `192.168.1.9`. | [opt §4], [nexi F5] | Run [opt Appendix A.4] live check; then document-or-remove each; add LiteLLM route for 8083 only if vision becomes real; fix provider entry. |
| A23 | **No CI anywhere** (parent + both submodules): path-flattening regressions and secret leakage have no automated guard — A2 slipped through partly because of this. | [dep G7] | Minimal workflow: pytest + secret scan (gitleaks-class) + `*.env` tracking check. |
| A24 | **UI identity contradiction:** CSS self-labels itself *"Apex palette"* (`globals.css:4,293`) while positioning demands counter-narrative minimalist chartreuse. Decision gates every other UI item. | [ui §5/§7.1] | Decide direction first (→ D10); if Apex style wins, delete the counter-narrative positioning note so docs stop contradicting code. |
| A25 | **Fake-state indicators mislead operators:** ParticleHumanoid/Waveform/orb-halo animate identically whether backend is up or down; "tracking subsystem online" is a hardcoded string; `alert: memoryCount > 0` permanently paints amber for normal memory hits. | [ui §2/§7.3] | Wire or cut decorations; repurpose alert semantics for genuinely attention-needing events (pair with A5 UI surface). |
| A26 | **`prefers-reduced-motion` absent everywhere** while app runs infinite animations (orb halo, scanlines, 1400-particle rAF loop). Top accessibility gap. | [ui §4] | Add media-query guards; pause rAF loops under reduce. |
| A27 | **State-carrying borders fail non-text contrast** (cyan-300/20 at 1.54:1 vs required 3:1) — borders that distinguish online/offline nodes are illegible. | [ui §3b] | Raise alpha to ≥45% on state-carrying borders. |
| A28 | **ExecPolicy edge cases unpen-tested:** allowlisted `pytest` = arbitrary-code vector if a malicious test file lands; broad `curl -s` prefix fragile if any GET endpoint ever mutates; prefix-match bypasses untested. | [tool §1 residual] | Dedicated pen-test session (see Section D, follow-up #2); tighten allowlist after. |
| A29 | **Hollow LangGraph context:** `assemble_context` passes all-None stores (`pipeline_graph.py:49-59`) despite injection support — decisions made with empty episodic/entity context when flag is on. Stub-acceptable now. | [core F7] | Inject real stores before real-tool wiring. |

### LOW

| # | Item | Sources | Fix direction |
|---|------|---------|---------------|
| A30 | pytest config footgun: passing any arg under `nexi/` adopts `nexi/pyproject.toml` (no pythonpath) → `ModuleNotFoundError`; AGENTS.md's own documented commands hit it. Confirmed pre-dating migration. | [mem Item C, NF#6] | Delete colliding `[tool.pytest.ini_options]` or add `pythonpath=[".."]`; fix AGENTS.md examples. |
| A31 | Docs/config housekeeping bundle: MIGRATION.md pre-flattening paths + outdated manifest; `v0.1` is branch-not-tag; agentmemory "dropped" commit wording vs retained-curated reality; fakeredis claimed-not-declared; `~/.claude/CLAUDE.md` doesn't exist; opencode.jsonc Linux-absolute paths broken on Mac; NEXTAUTH_URL wrong subnet (`192.168.1.10:3000` → should be `192.168.50.1:3000`); openclaw unit still wired to k3s.service; legacy `infra/k8s/` tree unmarked; perception/vault-indexer units ship broken ExecStarts with no warning banner; AGENTS.md package layout missing goal/, eval/, character/, proactivity/. | [dep S5/S7], [mem NF#6], [nexi F5] | One docs-sweep PR; banner-comment disabled units; commit re-baselined workstream plan ([dep S6]). |
| A32 | Code nits: absolute `nexi.*` imports inside `xnch/agents/` violate conventions; `complete_step` read-modify-write unguarded cross-process; unbounded `progress` string; `/execution/execute` accepts unvalidated dict; dead getattr branches in `_fire_nexi_callback`. | [core F8/F9/F10] | Batch cleanup PR before real-tool wiring. |

---

## Section B — Contradictions Found

**B1 · Node B inference stack status** — deployment says done; optimize says diverged-and-unverified.
> [dep §4 row 2]: "**done** — `vllm-ornith.service`, `setup-gpu-driver.sh`, `start-node-b.sh`; MIGRATION notes dated Aug 2026 describe live tuning"
> [opt TL#2/#1]: "`--kv-cache-dtype fp8` and `--cpu-offload-gb` appear **nowhere in the repo**… util **0.95**, not 0.92" / "~171 tok/s … **Not found** in any doc, commit msg, report, or session log"

*Resolution:* deployed ≠ tuned/verified. WS2 reality = "deployed, untuned, unverified."

**B2 · Kuzu/Redis verification vs health-signal coverage** — the user-flagged cross-check.
> [mem Item B]: "Redis TTL behavior post-migration | **CONFIRMED-OK** (code + fakeredis tests; live PTTL inspection STILL-UNVERIFIED — unreachable)"
> [obs §1]: "Hit ratio / evictions / expired-key behavior: **unmeasured**"; SPOF#1: "Redis dies silently → active sessions and 30 s execution tokens vanish"
> Corollary pair: [mem]: consolidation.timer "Correctly ordered ✓ … Persistent=true" vs [obs]: "consolidation.timer runs blind"; Kuzu "size/growth untracked."

*Resolution:* complementary, not factually opposed — but [mem]'s OK verdicts are code-level only, and [obs] proves no live channel exists that could catch divergence. Any reporting must downgrade these to "verified in code/tests, never in production."

**B3 · beeAI handoff doc vs two independent reviews**
> [beeai-handoff.md]: "**COMPLETE and verified.** beeAI orchestration path is wired into xnch as a feature-flagged FastAPI router."
> [tool §2]: "the entire path was deleted (`9b4f1c0`)… Zero code references outside misc/opencode/beeai-handoff.md"
> [nexi F4]: "survives only on local branch `feat/beeai-agent-orchestration`"

*Resolution:* handoff describes pre-Aug-17 state; annotate as historical (folded into A1).

**B4 · HITL governance "done" vs four findings**
> [dep row 11]: "HITL governance pipeline | **done** (recent)"
> [core F5]: "goals never route through the HITL interrupt at all"
> [obs TL#3]: "**No. The most security-critical path emits zero audit events, metrics, or traces — and pending gates have no timeout.**"
> [ui §2]: "HITL gate / scheduler / goal loop have zero UI representation"

*Resolution:* the interrupt mechanism itself works within a single pipeline run ([tool §1] confirms wiring + invariant test `test_hitl_mode_never_skips_interrupt`) — everything around it (goal-loop coverage, ops visibility, timeout, UI) does not exist. "Done" applies only to the narrowest reading.

**B5 · Goals subsystem "done" vs scheduler missing**
> [dep row 12]: "Goals subsystem (store, CRUD, driver loop, eval harness) | **done** (recent)"
> [core status table]: "Scheduler | ❌ **Not done.** … Nothing ever calls `claim_next_goal` — it's a manual endpoint (`routes/goals.py:83`). The autonomous loop cannot run unattended."

*Resolution:* store/CRUD/stub-runner/eval are real and tested; autonomy is not. Additionally an unresolved discrepancy between reviews themselves: [nexi F2] says nexi's lifespan starts "capability-refresh + goal-driver loops," while [core F4] says nothing consumes due goals — needs a targeted trace (→ D1).

**B6 · Memory/storage unification "done"**
> [dep row 5]: "Memory/storage unification (canonical store) | **done (v0)**"
> [mem Task3#2]: "Legacy SQLite `EpisodicStore` is still live … decision flow **dual-writes** both stores … Split-brain persistence = un-migrated residual."

*Resolution:* PG canonical reads mask an unmigrated write path; treat WS5 as partially complete.

**B7 · Context assembler "blocked" — deployment stale in the *opposite* direction**
> [dep row 6]: "Context assembler wiring (rich context into live pipeline, A2) | **blocked** (explicitly deferred)" citing QA_REPORT.md:43 built-but-disconnected
> [nexi runtime path]: "POST /nexi/chat → … assemble_context() [nexi/pipeline/context_assembler.py] ← persona enters here"
> [mem read path]: "assemble_context (…:95): L1 get_turns(20) · L2 retrieve_similar(top_k=5…) · L3 get_entity_by_name…"

*Resolution:* the assembler IS wired into the live gateway chat path today; deployment's reconstruction predates that wiring. Planning doc is stale here, not the code.

**B8 · Observability "in-progress"**
> [dep row 13]: "Observability (Langfuse tracing) | **in-progress** | langfuse v2 pinned + healthchecked in compose"
> [obs TL#2]: "Infra metrics stack? **Absent entirely.** Zero Prometheus/Grafana/Alertmanager/exporters repo-wide."

*Resolution:* "in-progress" describes one thin, currently-inert LLM-trace client sitting on top of a nonexistent metrics layer.

*Non-contradiction worth recording:* three reviews independently converged on the Langfuse finding (thin LLM-only traces, inert by default, cloud-host footgun) — highest-confidence dedupe in this reconciliation (A14).

---

## Section C — Workstream Reality-Check

Baseline: [dep]'s reconstructed table (canonical 14-workstream/~420h plan doc itself is **not committed to the repo** — [dep S6]; statuses below cross-referenced against all 8 reviews).

| WS | Planned status | Evidence verdict | Cross-review evidence |
|----|---------------|------------------|----------------------|
| 1 · Infra migration k3s→bare metal | done | ✅ holds | Path flattening verified clean across disk/units/Dockerfiles/scripts; ops gaps G1–G3 remain but migration itself done. [dep] |
| 2 · Node B inference stack | done | ⚠️ **overstated** | Boots and serves, but briefed flags never applied, util 0.95≠0.92, KV margin tight, throughput claim has no provenance, live state unchecked. [opt], [obs GPU] |
| 3 · Core QA bugfixes B1–B7 | done | ✅ holds | Corroborated by git history (e.g. outcome-payload fix `499649d`). [dep] |
| 4 · API surface (chat + clarify) | done | ✅ holds | Exercised live in e2e-test.sh. [dep] |
| 5 · Memory/storage unification | done (v0) | ⚠️ partial | Split-brain SQLite+PG dual-write persists; `xnch_memory_store_note` broken; tier edges impossible. [mem Task3, NF#1/#2] |
| 6 · Context assembler wiring | blocked | ⚠️ **stale — likely superseded** | Assembler wired into gateway chat path per two reviews. [nexi runtime path], [mem read path] |
| 7 · Orphaned services decommission | done | ✅ w/ asterisk | agentmemory retained as curated side-channel contradicting commit-message wording; mem0/zep artifacts still tracked in git. [mem Task3] |
| 8 · Execution runner | in-progress | ✅ holds | Dispatch stub emits events only; `/execution/execute` is simulation; graceful-fail shipped. [core status], [tool §1] |
| 9 · Perception service | not-started | ✅ holds | References nonexistent entrypoints; unit must stay disabled. [dep §3] |
| 10 · Vault indexer | not-started | ✅ holds | Same. [dep §3] |
| 11 · HITL governance pipeline | done | ⚠️ **overstated** | In-run interrupt works + invariant test; goals bypass it, zero telemetry, no timeout, zero UI. [tool §1], [core F5], [obs], [ui] |
| 12 · Goals subsystem | done | ⚠️ **overstated** | Store/CRUD/eval done; scheduler missing → cannot run unattended. [core F4] |
| 13 · Observability | in-progress | ⚠️ generous | Metrics stack absent entirely; tracing thin/inert/cloud-host-defaulted. [obs], [mem Task4] |
| 14 · Security hardening | blocked | ✅ strongly corroborated | Now larger than planned: adds agent-gateway fail-open (A3), bare routers (A4), no CI (A23). [dep S1/S3], [core F1–F3] |

**Bottom line:** genuinely remaining P0 ≈ row 14 (security) + row 8 (runner) + row 13 (observability scope) + boot/health ops gaps — consistent with [dep]'s wave note. Rows 9–10 should be formally re-scoped or dropped rather than carried as open hours. Commit the re-baselined plan so future audits can diff against it ([dep S6]).

---

## Section D — Open Questions Requiring Follow-Up

**Live tests (all three technical audits were repo-only / off-LAN):**
- **D1** — Does anything consume due goals in production? [core F4] says nothing calls `claim_next_goal`; [nexi F2] says nexi lifespan starts "goal-driver loops." Trace nexi's driver → does it hit xnch's claim API or is it a stub? Blocks A6 design. *(best candidate for the 9th targeted session)*
- **D2** — Node A batch: live Redis PTTL sweep (`redis-cli --scan | xargs redis-cli pttl`); consolidation.timer enabled?; disposition of `.chroma_db/`, `SESSIONS`, legacy `~/.xnch/xnch.db`. [mem close-out #8]
- **D3** — Node B batch: actual vllm cmdline vs repo unit file (drift check); KV-cache-size/concurrency startup logs; `gpu_cache_usage_perc`; whether :8083 (Qwen-VL) and :8081 (llama.cpp) run at all. [opt Appendix A]
- **D4** — Benchmark truth: confirm/refute "~171 tok/s" and record baseline per opt Appendix B template.

**Human decisions (not guessable):**
- **D5** — Leaked credentials: rotate-only vs git-history rewrite. [dep §7 explicitly defers to operator]
- **D6** — Sign off WS6 as superseded (assembler wiring) and update plan.
- **D7** — Bi-temporal invalidation: implement on Kuzu or descope + correct docs. [mem #1]
- **D8** — Proactivity engine: wire `check_and_queue` into a lifespan/timer loop or delete the engine entirely. [nexi rec #3]
- **D9** — beeAI PoC: resurrect deliberately (branch `feat/beeai-agent-orchestration` exists) or archive the fossil + annotate `beeai-handoff.md` as pre-deletion history. [tool §2, action 4]
- **D10** — UI identity: Apex-style navy/cyan HUD vs brief's minimalist black/chartreuse. Gates every other UI item (A24–A27). [ui §7.1]
- **D11** — SQLite EpisodicStore fate: full migration to PG or accept dual-write permanently. [mem close-out #5] (pairs with A13)
- **D12** — Perception/vault-indexer workstreams: formally re-scope or drop rather than carry open hours. [dep §4]

**External watch:**
- **D13** — Apex "full reveal": differentiator claim is currently unfalsifiable (marketing-only evidence). Re-verify at their public launch before re-using it in any interview setting. [tool §4]

**Candidate 9th targeted follow-up sessions:**
1. **Goal-driver trace** (D1) — resolves the one genuine review-vs-review discrepancy; unblocks A6.
2. **ExecPolicy pen-test** (A28) — pytest ACE vector, `curl -s` GET-mutation, prefix bypasses. [tool action 5]
3. **HITL end-to-end live exercise** after A5 instrumentation lands — open gate → approve → resume; verify counters, sweeper, and alert fire.
4. **Persona adversarial red-team** once A8 hardening ships (objection re-litigation, sycophancy bait, persona-suppression probes). [nexi rec #5]
5. **Firefox manual browser pass** — [ui §4 checklist] requires a human with a browser; no automation existed in that session.

---

**Reconciliation complete.** Headline for whoever picks this up: fix the narrative first (A1), rotate secrets second (A2), then the gateway and authn pair (A3/A4) — everything else can proceed in listed order without blocking. The single most important structural insight from running 8 independent reviews: **every review found its component's "flagship" feature partially real** (PolicyFilter unified but story stale; HITL interrupt works but invisible and goal-blind; memory tiers wired but split-brained; GPU serving but untuned) — so trust no "done" label in the plan doc until Section C's evidence column says otherwise.
