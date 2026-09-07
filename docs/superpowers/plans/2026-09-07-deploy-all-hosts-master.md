# Deploy `master` to all 3 hosts (node-a, node-b, mac web)

## Objective

Ship the uncommitted (plus local-only) state of the repo to all three hosts:

- **node-a** (192.168.1.10): `xnch.service` on :8001 — gateway, workflow store, permissions, policies
- **node-b** (192.168.1.9): `nexi.service` :8000 + `vllm-ornith.service` :8082 — engine, persona, model routing, workflows
- **mac**: `web/` — keep running via `next dev` (no launchd/service change)

Branch: **`master`**. Everything gets committed first (superproject + nexi + xnch), submodule
masters are pushed to GitHub, then `scripts/deploy.sh` pushes to both nodes and restarts services
(including vLLM). Mac web is a manual `npm run dev` restart; no new deploy mechanism added.

## Context / decisions

- Both nodes are on `master` at `25e937c` (ancestor of HEAD → node pushes are clean fast-forwards).
- Node pins: nexi `eefe005` (FF-ancestor of our new SHA), xnch `51a315c` (= our base). No bootstrap needed.
- Superproject `master` is ahead 12 / behind 3 of origin/master. The 3 origin commits (apex-ui merge
  `2d809c3`, xnch gitlink `f02a041`→`8f74a81`, gitignore `e245c93`) do **not** touch our web files.
  **Decision: do NOT fetch/merge them and do NOT force-push GitHub master** (would drop the public apex
  merge / rewrite history). Superproject reaches nodes via direct SSH push; only submodule SHAs need GitHub.
- `deploy.sh` `publish()` runs `cat-file -e` on `NEXI_WT`/`XNCH_WT` — override them via env vars to the
  local submodule clones so the created SHAs are found. Use `--skip-publish` so the superproject is never
  pushed to GitHub.
- vLLM: restart requested → pass `--restart-vllm`.
- Deps: nexi `uv.lock` changed (in-submodule); deploy.sh's `--sync-deps` only inspects superproject-level
  `pyproject.toml`/`uv.lock`, so it can't trigger for this. Covered by a manual node-side check (see Task 6).

## Files / repos touched

| Repo | Path | Change |
|------|------|--------|
| nexi (submodule) | `adapters/model_router.py`, `adapters/model_adapter.py`, `adapters/llm.py`(new), `pipeline/*`, `config.py`, `character/persona_builder.py`, `eval/grader.py`, `workflow/executor.py`, `run.py`, `uv.lock`, tests | commit → push master |
| xnch (submodule) | `config.py`, `memory/workflow_store.py`, `models/workflow.py` | commit → push master |
| superproject | `web/*` (gateway route, sidebar, workflow canvas, lib/api, lib/workflows), `xnch_mcp/chat_tools.py`, `agent-runner/`, `opencode.jsonc`, `infra/dify-xnchsystems-template.yml`(del), untracked (`scripts/workflows/`, `scripts/reddit/`, `deepseek-harness/`, `web/doc_product`, context panel) | commit (gitlinks) → SSH-push via deploy.sh |
| nodes | `~/xnchSystems` (superproject + submodule checkouts) | updated by deploy.sh |

## Entry / exit criteria

- **Exit preflight (before any commit):**
  1. `git status --short` superproject + both submodules reviewed and intentional
  2. nexi tests green: `PYTHONPATH=. .venv/bin/python -m pytest nexi/tests`
  3. xnch tests green: `.venv/bin/python -m pytest xnch/tests`
  4. superproject tests green: `.venv/bin/python -m pytest tests xnch_mcp/tests`
  5. node-a `http://192.168.1.10:8001/health`, node-b `http://192.168.1.9:8000/health` OK
- **Success (post-deploy):**
  1. node-a `http://192.168.1.10:8001/health` OK
  2. node-b `http://192.168.1.9:8000/health` OK, `:8082` vllm responding
  3. mac `http://localhost:3000` next dev up; gateway proxy passes to node-a (gated prefixes: workflows/approvals/agents)
  4. Functional: `xnch_mcp chat_tools` (spotify) reachable; workflow canvas loads; mode/router config applied

## Task 1 — Commit nexi work, push master to GitHub

In the nexi submodule (currently detached HEAD at `1063925`, no local `master`):

```bash
cd /Users/xnch/xnchSystems-agentic-10/nexi
git checkout -B master                 # create local master at 1063925
git add -A
git commit -m "feat: model router, workload-driven persona, workflow executor + eval updates"
git push -u origin master              # FF over origin/master (eefe005)
```

Verify: `git log --oneline -1 origin/master` shows the new commit; `git merge-base --is-ancestor
eefe005 HEAD` exits 0.

## Task 2 — Commit xnch work, push master to GitHub

In the xnch submodule (detached at `51a315c` = origin/master):

```bash
cd /Users/xnch/xnchSystems-agentic-10/xnch
git checkout -B master
git add -A
git commit -m "feat: workflow store + workflow model updates"
git push -u origin master              # FF over 51a315c
```

Verify: `git merge-base --is-ancestor 51a315c HEAD` exits 0; origin/master == HEAD.

## Task 3 — Commit superproject (incl. new submodule gitlinks) on master

```bash
cd /Users/xnch/xnchSystems-agentic-10
git add nexi xnch                      # stage new pinned SHAs
git add -A                             # all tracked + untracked work
git status                            # eyeball the full staging set (incl. untracked dirs)
git commit -m "feat: workflow canvas (WS4), chat_tools spotify bridge, gateway + ops updates"
```

Do **not** push to GitHub. Verify: `git ls-tree HEAD nexi` == HEAD of nexi master (from Task 1);
`git ls-tree HEAD xnch` == HEAD of xnch master (Task 2).

## Task 4 — Mac web: stop/start `next dev` (keep dev mode)

Web code is already in the working tree (mac runs the repo in place); no git change needed on mac.

```bash
# stop existing dev server if running (check :3000)
lsof -ti :3000 | xargs kill 2>/dev/null || true
cd /Users/xnch/xnchSystems-agentic-10/web
npm run dev
```

Verify: `curl -s localhost:3000` returns the app shell; `web/.env.local` still points
`XNCH_GATEWAY_URL=http://192.168.1.10:8001` (unchanged).

## Task 5 — Deploy to node-a + node-b

```bash
cd /Users/xnch/xnchSystems-agentic-10
NEXI_WT="$PWD/nexi" XNCH_WT="$PWD/xnch" \
  ./scripts/deploy.sh all \
  --branch master \
  --skip-publish \
  --restart-vllm
```

Expected:
- `publish()` verifies pinned SHAs against local submodule clones (pass), no GitHub pushes.
- node-a: `xnch.service` restarted, health `:8001` OK.
- node-b: `nexi.service` restarted, vllm restarted, health `:8000` OK (timeout up to `VERIFY_TIMEOUT`).
- Node-local diffs backed up to `~/xnchSystems.deploy-backup.*.tar.gz` (should be empty/clean).

## Task 6 — Node-side dependency + submodule sanity

deploy.sh can't sync in-submodule dep changes, so verify module imports work on node-b:

```bash
ssh node-b "~/xnchSystems/nexi/.venv/bin/python -c 'import nexi.adapters.model_router, nexi.adapters.model_adapter, nexi.character.persona_builder'"
ssh node-b "curl -sf -m 5 http://localhost:8082/v1/models | head -c 200"
ssh node-a "curl -sf -m 5 http://localhost:8001/health"
```

If the import fails on a missing dependency (e.g. new dep in `uv.lock`), run on the node:
`uv pip install --python ~/xnchSystems/nexi/.venv/bin/python -e ~/xnchSystems/nexi` then restart
`nexi.service`. Record the outcome in the review.

## Task 7 — End-to-end verification (from mac)

```bash
# 1. gateway through web proxy (gated prefixes)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/api/gateway/mcp/tools
curl -s http://localhost:3000/api/gateway/workflows        # expect JSON list or 200
# 2. direct node-a gateway
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.1.10:8001/health
# 3. chat_tools / spotify bridge exposed through gateway
#    (via UI: chat panel shows spotify tool available; or xnch_mcp smoke)
./scripts/smoke_runners.sh 2>/dev/null || true   # if exists, else manual:
```

Manual/console checks: open http://localhost:3000 — workflows canvas renders past WS1–WS4 nodes; chat
sidebar lists spotify-controlled tools; open the entity/context panel. Run the existing suites once more
to confirm nothing regressed in the committed tree.

## Rollback

- Superproject on nodes: `git -C ~/xnchSystems checkout -f master` at the prior SHA `25e937c`, then
  `submodule update --init --recursive --force`, restart services with prior units, restore
  `~/xnchSystems.deploy-backup.*.tar.gz` if any node-local work was lost.
- No GitHub history was rewritten (superproject never pushed; submodule pushes were fast-forwards), so
  any public ref can be reset with `git reset --hard <old-sha>` on the affected branch.

## Open risks

1. Untracked big dirs (`deepseek-harness/`, `web/doc_product`, `scripts/reddit/`) get committed per
   "commit everything" — confirm at Task 3 staging review that this is intended.
2. `--sync-deps` can't see submodule `uv.lock` changes → Task 6 might surface a missing dep at runtime.
3. Pre-existing tsc error in `web/src/app/api/gateway/[...path]/route.ts:85` (Buffer vs BodyInit) is
   unaffected by this deploy; next dev runs it in dev mode regardless.
4. Origin/master apex-ui branch stays on GitHub only (not merged/deployed) — intentional.