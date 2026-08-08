# Nexi command execution (deploy)

Tool: `xnch_exec_run` (T2, `nexi` / `operator` / `admin` only).

## Policy

`~/.xnch/exec-policy.yaml` (from `infra/no-k3s/shared/exec-policy.yaml`)

- Allowlist prefixes per host (systemctl status, journalctl, curl, git, pytest, …)
- Denies: `;|&`, sudo, rm, kubectl apply, terraform apply, systemctl start/stop/restart

## Env (gate7 `~/.xnch/xnch.env`)

```
XNCH_EXEC_POLICY_PATH=/home/x-nch/.xnch/exec-policy.yaml
XNCH_EXEC_AGENT_NODE_B_URL=http://192.168.50.2:8004
XNCH_EXEC_AGENT_TOKEN=<shared-secret>
```

## node-b

```bash
sudo cp infra/no-k3s/node-b/systemd/exec-agent.service /etc/systemd/system/
sudo systemctl enable --now exec-agent
# firewall: 192.168.50.1 → TCP 8004
```

## Verify

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_exec_run","arguments":{"host":"node-a","command":"systemctl is-active xnch.service"}}'
```

Extend allowlist by editing `exec-policy.yaml` on both nodes and restarting xnch / exec-agent.

Current groups: systemd status/logs, curl health probes, docker read-only, git read-only, CLI diagnostics, redis/pg probes, system introspection (ss, ip, df, nvidia-smi on node-b).
