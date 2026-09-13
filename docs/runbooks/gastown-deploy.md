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

~~The legacy `com.xnch.agent-runner` LaunchAgent is retired once Gas Town is live.~~

**Status: COMPLETE (2026-09-13)** — agent-runner retired; Gas Town is sole Mac-side workstream runner.

```bash
launchctl bootout gui/$(id -u)/com.xnch.agent-runner 2>/dev/null
rm -f ~/Library/LaunchAgents/com.xnch.agent-runner.plist
launchctl list | grep -i agent-runner || echo "retired"
```

### M3.4 retirement evidence (2026-09-13)

- **Workstream:** `ws-9f00536b`
- **Bead:** `xnch-workstreams-dlv`
- **Final state:** `running`
- **Smoke test:** 201 on POST /api/workstreams; bead created; dispatch_error: null
- **Note:** agent-runner plist removed. Gas Town bridge (`com.xnch.gastown`) + tunnel (`com.xnch.gastown-tunnel`) remain active as the sole dispatch path.

## Rollback

```bash
launchctl unload ~/Library/LaunchAgents/com.xnch.gastown.plist
```

## Dispatch chain verified (2026-09-13)

Full hermes → gateway (node-a:8001) → bridge (Mac:7474) → bead → convoy → sling → running chain verified end-to-end.

- **Workstream:** `ws-9e5d5408`
- **Bead:** `xnch-workstreams-24a`
- **Final state:** `running`
- **Bridge log evidence:** `22:36:42 POST /api/workstreams 201`
- **Old token (tail ...Y4bcs):** 401 at both gateway and bridge
- **New token (tail ...c604):** 200 at both hops

### Fixes applied this round
1. **node-a gateway env** — appended `XNCH_GASTOWN_URL=http://127.0.0.1:7474` + `XNCH_GASTOWN_TOKEN` to `~/.xnch/xnch.env`; restarted `xnch.service`.
2. **SSH reverse tunnel** — `ssh -fN -R 7474:127.0.0.1:7474 x-nch@node-a` makes node-a's localhost:7474 forward to the Mac's loopback-only bridge.
3. **Bridge launchd PATH** — added `EnvironmentVariables.PATH` to `com.xnch.gastown.plist` so `gt`/`bd` are found.
4. **`_gt_exists()` guard** — changed from `subprocess.run(["gt","status"])` (hangs under non-tty) to `shutil.which("gt")`.

## Tunnel durability (autossh + KeepAlive)

The ephemeral SSH reverse tunnel (`ssh -fN -R`) does not survive reboots or connection drops. Replace it with a launchd `KeepAlive` wrapper around `autossh`:

1. Install autossh: `brew install autossh`

2. Create `~/Library/LaunchAgents/com.xnch.gastown-tunnel.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.xnch.gastown-tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/autossh</string>
        <string>-M</string>
        <string>0</string>
        <string>-N</string>
        <string>-o</string>
        <string>ServerAliveInterval=30</string>
        <string>-o</string>
        <string>ServerAliveCountMax=3</string>
        <string>-o</string>
        <string>StrictHostKeyChecking=no</string>
        <string>-R</string>
        <string>7474:127.0.0.1:7474</string>
        <string>x-nch@node-a</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/xnch/.xnch/gastown-tunnel.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/xnch/.xnch/gastown-tunnel.err</string>
</dict>
</plist>
```

3. Load it: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.xnch.gastown-tunnel.plist`

4. Verify: `launchctl print gui/$(id -u)/com.xnch.gastown-tunnel` → `state = running`, pid present.

5. Kill any old ephemeral tunnel: `pkill -f "ssh.*-R 7474"` — confirm only `autossh` remains.

**Notes:**
- `-M 0` disables autossh's own monitoring (SSH's `ServerAliveInterval`/`ServerAliveCountMax` handles liveness).
- Adjust the autossh path for Intel Macs (`/usr/local/bin/autossh`).
- Logs: `~/.xnch/gastown-tunnel.log` (stdout), `~/.xnch/gastown-tunnel.err` (stderr).

---

**Reference:** Plist template at `clients/gastown/com.xnch.gastown.plist`.
