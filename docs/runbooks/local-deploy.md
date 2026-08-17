# Local Deploy — node-a / node-b (git push-to-deploy)

Push the current branch from the Mac to node-a / node-b over SSH. No rsync,
no scp. GitHub is the source of truth; the deploy script publishes the branch
first, then pushes to each node's `~/xnchSystems` clone (which updates the
live worktree via `receive.denyCurrentBranch=updateInstead`), syncs
submodules, restarts affected services, and verifies health.

Applies to the **`feat/ornith-cli-voice`** branch (ornith-only: no web/mac/media stack).

## Topology

| Node | SSH alias | Reachable from Mac | Services |
|------|-----------|--------------------|----------|
| Node A (gate7) | `node-a` (`192.168.1.10`) | LAN | docker compose (litellm, redis, postgres, langfuse, searxng) + `xnch.service` (:8001) |
| Node B | `node-b` (`192.168.1.9`) | LAN | `vllm-ornith.service` (:8082), `nexi.service` (:8000) |

## One-time bootstrap

Run from the ornith worktree (branch must be checked out locally):

```bash
cd ~/xnchSystems-ornith

# clone + set up a node (or both):
./scripts/deploy.sh --bootstrap node-a
./scripts/deploy.sh --bootstrap node-b
./scripts/deploy.sh --bootstrap all
```

What bootstrap does on the node:
- Backs up a non-git `~/xnchSystems` to `~/xnchSystems.bak.<timestamp>`, then
  `git clone --branch feat/ornith-cli-voice` from GitHub.
- `git submodule update --init --recursive`.
- Sets `git config receive.denyCurrentBranch updateInstead` (allows SSH push
  to update the live worktree; **refuses push if the worktree has uncommitted
  changes** — keep node-local config in `~/.xnch/*.env`, not the repo).
- Publishes the branch to GitHub first (superproject + `nexi`/`xnch`
  submodules), since the clone needs the branch to exist upstream.

## Deploy

```bash
cd ~/xnchSystems-ornith
./scripts/deploy.sh node-a            # xnch + compose/litellm on node-a
./scripts/deploy.sh node-b            # nexi (+ vllm with --restart-vllm) on node-b
./scripts/deploy.sh all               # both
```

Options:

| Flag | Effect |
|------|--------|
| `--branch NAME` | Branch to publish/deploy (default `feat/ornith-cli-voice`) |
| `--wake` | If node-b is down, WoL it from node-a first (`wake-node-b.sh`) |
| `--sync-deps` | `uv pip install` into node venvs when `pyproject.toml`/`uv.lock` changed |
| `--restart-vllm` | Restart `vllm-ornith` on node-b even if its unit didn't change |
| `--skip-publish` | Skip GitHub push; only verify commits exist upstream |

Pipeline per node:
1. **Publish** — `nexi`/`xnch` submodule worktrees + superproject pushed to GitHub
   (`/Users/xnch/nexi-ornith`, `/Users/xnch/xnch-ornith`, current worktree).
   Verify pinned submodule SHAs are reachable.
2. **Push** — `git push node-a:~/xnchSystems feat/ornith-cli-voice` (same for node-b).
3. **Sync** — `git submodule update --init --recursive` on the node.
4. **Restart (path-diff driven):**
   - node-a: `xnch.service` always; `docker compose up -d` + `restart litellm`
     when compose/litellm/searxng/shared-routing changed; reinstall systemd
     units when `node-a/systemd/` changed.
   - node-b: `nexi.service` always; `vllm-ornith` on unit change or `--restart-vllm`;
     reinstall units when `node-b/systemd/` changed.
   - `--sync-deps`: uv install into `xnch/.venv` (A) / `nexi/.venv` (B).
5. **Verify** — curl `:8001/health` (A) / `:8000/health` (B) from each node.

## Workflow

```bash
cd ~/xnchSystems-ornith && git add -A && git commit -m "change"
./scripts/deploy.sh all
```

> **Submodules:** node fetches pinned SHAs from GitHub, so submodule changes
> must be committed and the deploy will publish them. If a submodule commit
> isn't pushed, deploy fails at the preflight check with a clear SHA error.
> Commit in `/Users/xnch/nexi-ornith` / `/Users/xnch/xnch-ornith` worktrees.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `push rejected (dirty worktree?)` | Node has uncommitted changes; commit them there or reset. Node-local config belongs in `~/.xnch/*.env`. |
| `~/xnchSystems is not a git clone` | Run `./scripts/deploy.sh --bootstrap <node>`. |
| Submodule SHA error at publish | Commit/push the submodule from its worktree first. |
| node-b unreachable | `./scripts/deploy.sh all --wake` (WoL via node-a). |
| litellm 401 on `/health` | Expected — use `/health/liveliness` (unauth). |
| New unit file added | Only files named in the script's reinstall step are copied; add new units to `deploy.sh` `restart_services` if needed. |
