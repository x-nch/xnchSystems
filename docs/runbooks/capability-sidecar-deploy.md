# Capability sidecar deploy (node-b)

Replaces `exec-agent.service` (:8004) and `fs-read-agent.service` (:8003)
with one `xnch-capability.service` on :8090.

## Preconditions
- This repo deployed on node-b with Tasks 2-6 merged (capability_agent package + retargeted clients).
- Port 8090 free on node-b: `ss -ltn | grep 8090` → empty.

## Cutover (node-b)
1. Set the shared token in `/home/x-nch/.xnch/nexi.env`:
   `XNCH_CAPABILITY_TOKEN=<same value as XNCH_EXEC_AGENT_TOKEN>`
2. Install the unit:
   ```
   sudo cp infra/no-k3s/node-b/systemd/xnch-capability.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now xnch-capability
   curl -s http://127.0.0.1:8090/health   # {"status":"ok","capabilities":"exec,fs"}
   ```
3. Old units stay running (dual-run window) until step 5.

## Flip callers (node-a + any xnch_mcp host)
4. In the env of every process running xnch_mcp (xnch gateway env file):
   ```
   XNCH_CAPABILITY_NODE_B_URL=http://192.168.50.2:8090
   XNCH_CAPABILITY_TOKEN=<shared token>
   ```
   Restart the xnch gateway. Verify: `python -m clients.cli mcp test --skip-chat` — exec/fs tool tests pass.

## Decommission (node-b)
5. Stop old units:
   ```
   sudo systemctl disable --now exec-agent fs-read-agent
   ```
6. Update the deployed exec policy allowlist on BOTH nodes (`~/.xnch/exec-policy.yaml`): curl entries :8003/:8004 → :8090.

## Rollback
- Unset `XNCH_CAPABILITY_NODE_B_URL` (or set it empty) and restart the gateway —
  clients fall back to `XNCH_EXEC_AGENT_NODE_B_URL` / `XNCH_FS_AGENT_NODE_B_URL`.
- `sudo systemctl start exec-agent fs-read-agent` (units kept until Phase 1 cleanup is confirmed stable).