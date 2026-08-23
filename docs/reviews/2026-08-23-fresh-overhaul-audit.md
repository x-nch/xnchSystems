# Documentation Fresh-Overhaul Audit — 2026-08-23

Point-in-time record of the Phase 0 audit that preceded the docs rebuild on
branch `docs/fresh-overhaul` (parent @ 168878f; submodules xnch @ cef5578,
nexi @ cbd9246). Evidence base: code-review-graph full build (527 files /
3,224 nodes / 23,012 edges / 13 communities), direct source reads, systemd
units, git log.

## Verdicts

| Verdict | Files |
|---|---|
| REWRITE | root `README.md` (described retired k3s regime, Gemma/mem0/zep era, env tables 20/18 vs actual 71/38 config fields) |
| DELETE→REWRITE | `web/README.md` (create-next-app boilerplate) |
| KEEP | `docs/architecture-suite.md` (now superseded by `docs/architecture/*`, stub redirect left in place); `infra/README.md`; 5 runbooks; guides (`memory-routing`, `nexi-test-prompts`, `mcp-cli`, voice ×3); reference mcp-* ×3 |
| RELOCATED | `docs/guides/mcp-bridge.md` → `docs/architecture/mcp-bridge.md` |
| IMMUTABLE (link-only) | `docs/adr/**`, `docs/superpowers/**`, prior reviews/audits |
| ARCHIVE (marked, not deleted) | `infra/k8s/**` legacy manifests |

New tree written: root README; docs/index; architecture/{overview, topology,
memory, decision-pipeline, workflows-hitl, data-model, training, mcp-bridge};
guides/{quickstart-dev, deploy-node-a, deploy-node-b, operate-hitl,
build-workflow, chat-and-tools, voice, run-eval}; reference/{index, api-xnch,
api-gateway-chat, auth-model, env-vars, config-files, cli-reference, tests};
runbooks/{restart-node-a, restart-node-b, gpu-window, wake-node-b, e2e-smoke,
rollback}; package READMEs for `xnch-train/` + `web/`.

## Gaps closed

Gateway Hybrid-B token model; workflows/approvals API (14 endpoints);
executor claim-lease semantics (`nexi-wf-executor`, TTL 120 s, expiry-release,
RETRYING backoff); xtrain usage (flags verified against source); muse ops
(proxy env, Vercel SSE); Node B unit inventory incl. exec/fs agents; goals API;
tier-graph endpoints; exhaustive env reference.

## Contradictions found (code wins)

1. **No `Conflicts=` systemd exclusivity group exists in-repo** despite the
   training ADR asserting one ("Ornith vs Vision Media Stack"); only
   After=/Wants= ordering. Documented as manual GPU-window protocol.
2. Training ADR calls xnch-train a "top-level submodule"; it is an ordinary
   package (`.gitmodules`: xnch, nexi only).
3. Root README self-inconsistency: xnch port 8000 vs 8001 across sections;
   vLLM "Gemma 4 26B :8000" vs actual Ornith :8082.
4. `XNCH_POSTGRES_URL` source default embeds credentials (flagged as upstream
   hygiene bug; docs use placeholders).
5. Fresh-env CLI/test reality differs from old AGENTS-style claims: console
   scripts need the `xnch` submodule importable; fresh `uv sync` collects 460
   tests with 44 errors (missing redis/apscheduler/voice extras).

## Preserved known truths

Pre-existing test failures (`tests/test_voice_io.py`, `xnch_mcp` exec/fs
handler tests, `tests/test_nexi_chat_e2e.py`) are not regressions; xnch-train
gate is dry-run-only Phase 0; checkpoint promotion requires HITL.

## Open questions at ship time

- Where should muse be hosted long-term (Vercel vs gate7)? Docs cover both.
  *(Resolved same-day: muse runs on the operator's Mac — docs updated.)*
- ADR's `Conflicts=` group: implement units or amend ADR status?
- Submodule-side READMEs (xnch/, nexi/): initially out of scope; authored
  later the same day via parallel technical-writer agents. Integration review
  corrected three over-statements against code: `/memory/graph/tiers|all` are
  docstring-designed but unrouted; nexi holds no JWT-decode path (token
  enforcement lives in xnch `/execution/*`); workflow executor emits
  SUCCESS|FAILURE only (API additionally accepts PARTIAL).
