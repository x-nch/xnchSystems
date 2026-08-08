# Nexi read-only filesystem (deploy)

Nexi reads files via **xnch MCP tools** (`actor=nexi`). Node-a reads locally; node-b via `fs-read-agent`.

## Env (gate7 `~/.xnch/xnch.env`)

```bash
XNCH_FS_POLICY_PATH=/home/x-nch/.xnch/fs-policy.yaml
XNCH_FS_AGENT_NODE_B_URL=http://192.168.50.2:8003
XNCH_FS_AGENT_TOKEN=<shared-secret>
XNCH_FS_MAX_READ_BYTES=2097152
```

## Deploy policy (both nodes)

```bash
cp infra/no-k3s/shared/fs-policy.yaml ~/.xnch/fs-policy.yaml
```

## Node B — fs-read-agent

```bash
# On 192.168.50.2
sudo cp infra/no-k3s/node-b/systemd/fs-read-agent.service /etc/systemd/system/
# Firewall: allow 192.168.50.1 → TCP 8003 only
sudo systemctl daemon-reload
sudo systemctl enable --now fs-read-agent
```

Add same `XNCH_FS_AGENT_TOKEN` to `~/.xnch/nexi.env` on node-b.

## Restart xnch (gate7)

```bash
sudo systemctl restart xnch.service
```

## Verify

```bash
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: nexi' | grep xnch_fs

curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_fs_read","arguments":{"host":"node-a","path":"xnchSystems/xnch/main.py"}}'

curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_fs_read","arguments":{"host":"node-b","path":"xnchSystems/nexi/main.py"}}'
```

Paths are relative to `/home/x-nch` (use `xnchSystems/...` prefix for repo files).

## MCP tools (nexi only)

| Tool | Purpose |
|------|---------|
| `xnch_fs_list` | Directory listing |
| `xnch_fs_read` | Read file (2MB cap) |
| `xnch_fs_stat` | Metadata |
| `xnch_fs_exists` | Exists check |
| `xnch_fs_glob` | Glob under roots |

`opencode` / `external` actors do **not** see fs tools.
