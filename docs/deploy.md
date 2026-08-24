# Deploy Runbook — xnchSystems two-node + Mac

Last verified: 2026-08-23 (agent-dispatch deploy). Node roles:
- **node-a / gate7** (`192.168.1.10`): xnch API :8001, Postgres/Redis/LiteLLM/Langfuse (compose), consolidation.timer
- **node-b / xnch-core** (`192.168.50.2`): nexi :8000, vllm-ornith :8082 (systemd `Conflicts=` group — **never restart vllm as part of deploys**)
- **Mac**: muse dev server :3000, `agent-runner` (launchd), coding agents

---

## THE RULE (read this first)

**Never `git pull` while in detached HEAD.** A prior sha-checkout-style deploy left
node-a detached; the next `git pull` silently no-op'd ("Already up to date" against
nothing) or errored with tracking complaints, and drift went unnoticed until a later
sync failed loudly.

Every deploy starts with:

```bash
ssh node-a 'cd ~/xnchSystems && git checkout master && git fetch origin && git merge --ff-only origin/master'
```

If ff-merge refuses because of dirty files, check whether the incoming delta actually
touches them (gitlink-only bumps usually don't) — do NOT blanket-stash operator state.

## Standard deploy: superproject + submodule pointer bump

1. **Local**: commit submodule work on its branch → push branch → bump ptr in
   superproject (`git add <sub>` after checking out the new sha locally) → push master.
2. **node-a**:
   ```bash
   ssh node-a 'cd ~/xnchSystems \
     && git checkout master && git fetch origin && git merge --ff-only origin/master \
     && git submodule update --init <submodule> \
     && sudo systemctl restart xnch.service'
   ```
   Restart only when packaged code changed; yaml/config read live by prompt loaders.
3. **node-b** (nexi changes): same pull/submodule dance, then `sudo systemctl restart nexi.service`.
4. **Verify** (all must pass before declaring success):
   ```bash
   curl -s http://192.168.1.10:8001/health          # {"status":"ok",...}
   curl -s http://192.168.50.2:8000/health          # nexi ok
   ssh node-a 'grep -c XNCH_GATEWAY_SECRET ~/.xnch/xnch.env'   # must be 1 — empty secret = gated routes 503
   # route-specific probe for whatever shipped, e.g.:
   TOKEN=$(...)  # mint per docs/runbooks; reads are token-gated since 2026-08-24
   ```
5. **Rollback**: pre-deploy pins recorded in `~/xnchSystems.rollback.txt` per node;
   `git checkout -f <old-pin> && git submodule update --init --recursive` + service
   restart. Verify rollback with step 4 probes.

## Known footguns

| Footgun | Symptom | Fix |
|---|---|---|
| Detached HEAD + pull | silent no-op / tracking error | checkout branch first (THE RULE) |
| Empty `XNCH_GATEWAY_SECRET` on node-a | every gated route (agents/approvals/workflows, reads AND writes) returns **503** | set the secret in `~/.xnch/xnch.env`; `XNCH_ALLOW_OPEN_GATEWAY=1` only for throwaway dev |
| muse decides 403 on elevated approvals | xnch requires `X-Actor-Role: admin`; old muse build omits it | deploy web alongside/after the xnch hardening branch |
| Dispatched run picks wrong LLM provider | workspace `opencode.json` policy (written by agent-runner) denies all but `xnch-litellm` → node-a LiteLLM → node-b vllm ornith; do not bypass with raw `-m <provider/model>` flags — that proposal was rejected (LiteLLM-audit-trail rule) | keep `XNCH_AGENT_ARGS=run --agent xnch-dispatch`, `XNCH_ALLOW_UNSCOPED_AGENT=0` |
| zsh eats unquoted `?` | `no matches found: ...?x=y` | quote curl URLs |
| launchd PATH | `No such file or directory: opencode` | absolute binary path in plist `EnvironmentVariables` |
| Python buffering under launchd | empty runner.log | `PYTHONUNBUFFERED=1` in plist |
| `uv sync --dev` in flat-layout submodules | hatchling "Unable to determine which files to ship" | `uv sync --dev --no-install-project` |
| Stale `.next` types after page moves | first web build fails referencing removed pages | `rm -rf web/.next && rebuild` |

## Submodule surgery (when working tree intentionally diverges)

If a submodule's checked-out sha must be recorded without moving its working tree
(operator WIP inside):

```bash
git update-index --cacheinfo 160000,<sha>,<submodule-path>
```

Then verify content-equality between deployed hand-edits and the target commit
*before* force-checking out (`git diff <sha> -- <files>`); identical ⇒ safe to
`checkout -f`.

## Mac agent-runner

```bash
# regenerate installed plist from template (fills placeholders)
python3 - <<'EOF'
from pathlib import Path
import subprocess
secret = subprocess.run(["grep","^XNCH_GATEWAY_SECRET=","web/.env.local"],capture_output=True,text=True).stdout.strip().split("=",1)[1].strip('"')
tpl = Path("agent-runner/com.xnch.agent-runner.plist").read_text()
out = tpl.replace("PLACEHOLDER_REPO","/Users/xnch/xnchSystems").replace("PLACEHOLDER_SECRET",secret).replace("PLACEHOLDER_HOME","/Users/xnch")
Path.home().joinpath("Library/LaunchAgents/com.xnch.agent-runner.plist").write_text(out)
EOF
launchctl unload ~/Library/LaunchAgents/com.xnch.agent-runner.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.xnch.agent-runner.plist
tail -f ~/xnch-agents/runner.log     # expect "[runner] <id> polling ..."
```

## Full verification battery (release-grade)

```bash
uv run pytest xnch-train/tests -q                     # 82 passed
PYTHONPATH=<repo> .venv/bin/python -m pytest xnch/tests -q   # ~466 passed (1 pre-existing goal-model failure)
cd web && npm run build && npx vitest run             # build ok, 4/4
pytest ../nexi/tests/test_workflow_executor.py -q     # 7 passed (from xnch dir)
```

Pre-existing failures that are NOT regressions: `tests/test_voice_io.py` (sounddevice),
`xnch_mcp` exec/fs handlers (cwd), `tests/test_nexi_chat_e2e.py` (OSError).
