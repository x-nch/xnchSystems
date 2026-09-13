# Gas Town — Deploy Runbook (Mac)

## Upstream install

Gas Town (github.com/gastownhall/gastown) — install per the [official Gas Town docs](https://gastownhall.github.io/gastown).

```bash
# macOS (Homebrew) — also installs bd and dolt as dependencies:
brew install gastown
# Required runtime for gt up (Mayor, Witnesses, Refineries, polecats):
brew install tmux
# Initialize the Gas Town HQ at the workspace root:
gt install ~/xnch-workstreams
gt doctor --fix
gt config default-agent opencode
```

## Environment setup

1. Create the env file with MCP bridge credentials:

```bash
cat > ~/.xnch/gastown.env <<'EOF'
XNCH_GASTOWN_URL=http://localhost:7474
XNCH_GASTOWN_TOKEN=<your-mcp-token-here>
EOF
chown xnch:staff ~/.xnch/gastown.env
chmod 600 ~/.xnch/gastown.env
```

- `XNCH_GASTOWN_URL` must match the address `GastownClient` connects to (set in `xnch/config.py` as `gastown_url`).
- `XNCH_GASTOWN_TOKEN` must match `XNCH_MCP_HTTP_TOKEN` on the xnch gateway (set in `xnch/config.py`).

2. Verify the HTTP API responds:

```bash
curl -H "Authorization: Bearer $XNCH_GASTOWN_TOKEN" \
  http://localhost:7474/api/workstreams
```

## launchd install

1. Copy the plist template and load:

```bash
cp clients/gastown/com.xnch.gastown.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.xnch.gastown.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.xnch.gastown.plist
```

2. Check service status:

```bash
launchctl list | grep com.xnch.gastown
tail -f ~/xnch-agents/gastown.log
```

3. If the service fails, verify:

```bash
# Plist path and WorkingDirectory are correct
cat ~/Library/LaunchAgents/com.xnch.gastown.plist
# Bridge script and WorkingDirectory exist
ls -la /Users/USER/xnchSystems/clients/gastown/serve.py
# gt runtime available
which gt
```

## Tailscale reachability (from node-a)

From node-a, verify the Mac's Gas Town HTTP API is reachable over tailscale:

```bash
curl -H "Authorization: Bearer $XNCH_GASTOWN_TOKEN" \
  http://<mac-ip>:7474/api/workstreams
```

## End-to-end verification

1. Spawn a workstream via the CLI or HTTP router:

```bash
python -m clients.cli xnch_workstream_spawn --title "test" --goal "verify"
# or curl with X-MCP-Token and X-Actor-Role: operator
```

2. Confirm the workstream appears on the Mac's Gas Town dashboard.

3. Check status:

```bash
python -m clients.cli xnch_workstream_status
# or
curl -H "Authorization: Bearer $XNCH_GASTOWN_TOKEN" \
  http://localhost:7474/api/workstreams
```

4. Terminal outcome findable via memory recall:

```bash
python -m clients.cli xnch_memory_recall "workstream test completed"
```

## agent-runner retirement

The legacy `com.xnch.agent-runner` LaunchAgent is retired once Gas Town is live.

```bash
launchctl unload ~/Library/LaunchAgents/com.xnch.agent-runner.plist
```

Leave the retired plist in the tree until M5 cleanup.

## Rollback

```bash
launchctl unload ~/Library/LaunchAgents/com.xnch.gastown.plist
```

---

**Reference:** Plist template at `clients/gastown/com.xnch.gastown.plist`.
