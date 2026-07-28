# K8s Homelab Setup — Phases 8-10 (OpenClaw & Access Layer)

> **OpenCode:** Phase 7 is complete. K3s cluster running with XNCH, Nexi, memory layers. Continue from Phase 8.

---

## Phase 7 Summary — What's Running Now ✅

**Cluster state:** K3s 2-node, all core pods deployed.

**Working:**
- xnch-deployment (routing, memory retrieval, gateway)
- nexi-deployment (character pipeline, intent → dispatch)
- postgres-pgvector (XnchMemory layers 2-3)
- redis (layers 0-1)
- litellm (LLM router)
- agentmemory (bare metal on gate7 — Claude Code / OpenCode memory)
- langfuse (observability)
- perception-daemonset (perception layer on i7)
- Traefik ingress (routes via xnch.local / llm.local / etc.)
- Scheduled jobs (consolidation @ 02:00, agentmemory-bridge @ 02:30)

**Issues found & fixed:**
- nexi Docker image was missing xnch package → Fixed: added COPY xnch/ + pip install -e
- vllm-gemma4 K8s pod/service deleted → Replaced with bare-metal systemd service on i9
- CoreDNS UDP cross-node issue → Workaround: hostAliases in nexi pod
- gemma4-llama systemd on i9 already running (llama.cpp TurboQuant) → Using as-is

**Known broken (Phase 7 incomplete):**
- zep pod: Error 14 (tiktoken cl100k_base download timeout) — requires pre-download or local embedder

**Services accessible:**
- XNCH: ClusterIP 10.43.x.x:8001, NodePort 30800 (bare-metal)
- Traefik: ingress via xnch.local / llm.local / nexi.local / memory.local
- AgentMemory: http://192.168.1.10:3111 (API) + http://192.168.1.10:3113 (viewer)

---

## Phase 8 — Install OpenClaw on i7 (Always-On Gateway)

OpenClaw i7 runs as **systemd service** on bare metal — outside K8s. Connects to XNCH via NodePort 30800.

### 8a — Install OpenClaw binary on i7

```bash
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 "
  curl -fsSL https://openclaw.ai/install.sh | bash
  which openclaw
"
```

### 8b — Create i7.env with secrets

On **i7**, create `/home/x-nch/.openclaw/i7.env`:

```bash
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 "
  mkdir -p ~/.openclaw
  cat > ~/.openclaw/i7.env << 'EOF'
LITELLM_API_KEY=df4d178833bb37cac13628dcf2ce970e5d98e298f1c53eed8baadfe8e505b91d
AGENTMEMORY_SECRET=8244db5525f0064abe0bd03eb7f73fea38408270dcfa991cffde1d66b72c4037
EOF
  chmod 600 ~/.openclaw/i7.env
"
```

### 8c — Copy configs to i7

```bash
# Deploy openclaw/i7-config.yaml
sshpass -p xnch scp -o StrictHostKeyChecking=no \
  /Users/xnch/xnchSystems/infra/openclaw/i7-config.yaml \
  x-nch@192.168.1.10:/home/x-nch/.openclaw/i7-config.yaml

# Deploy openclaw/i7-start.sh
mkdir -p /tmp/openclaw-deploy
cp /Users/xnch/xnchSystems/infra/openclaw/i7-start.sh /tmp/openclaw-deploy/
chmod +x /tmp/openclaw-deploy/i7-start.sh

sshpass -p xnch scp -o StrictHostKeyChecking=no \
  /tmp/openclaw-deploy/i7-start.sh \
  x-nch@192.168.1.10:/home/x-nch/i7-start.sh
```

### 8d — Install systemd service

```bash
# Copy service unit
sshpass -p xnch scp -o StrictHostKeyChecking=no \
  /Users/xnch/xnchSystems/infra/openclaw/i7-systemd.service \
  x-nch@192.168.1.10:/tmp/openclaw-i7.service

# Install
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 "
  sudo cp /tmp/openclaw-i7.service /etc/systemd/system/openclaw-i7.service
  sudo systemctl daemon-reload
  sudo systemctl enable openclaw-i7
  sudo systemctl start openclaw-i7
  sleep 5
  sudo systemctl status openclaw-i7 --no-pager
"
```

### 8e — Verify i7 OpenClaw is running

```bash
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 "
  sudo systemctl status openclaw-i7 --no-pager
  curl -s http://localhost:30800/health || echo 'XNCH not responding yet'
"
```

### 8f — Set up Telegram (interactive step)

On **i7**, run:
```bash
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 "
  openclaw gateway setup
"
```

Follow the wizard:
1. Create Telegram bot via BotFather (@BotFather on Telegram)
2. Get bot token
3. Paste into OpenClaw setup
4. Confirm webhook registered

This creates a Telegram chatbot that OpenClaw i7 listens on. Messages come in → OpenClaw → XNCH → Nexi → Gemma4 → response → Telegram.

---

## Phase 9 — Configure Mac OpenClaw + AgentMemory Wiring

Your Mac is the **interactive surface** for OpenClaw. It also uses agentmemory to remember codebase decisions.

### 9a — Install OpenClaw on Mac

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
mkdir -p ~/.openclaw
```

### 9b — Copy Mac config

```bash
cp /Users/xnch/xnchSystems/infra/openclaw/mac-config.yaml ~/.openclaw/mac-config.yaml

# Verify the config points to i7 (192.168.1.10:30800)
cat ~/.openclaw/mac-config.yaml | grep base_url
```

### 9c — Set agentmemory env vars

```bash
# Copy env template
cp /Users/xnch/xnchSystems/infra/openclaw/claude-code-agentmemory.env ~/.openclaw/claude-code-agentmemory.env

# Source it before running Claude Code / OpenCode
cat >> ~/.zshrc << 'EOF'
# AgentMemory for coding
source ~/.openclaw/claude-code-agentmemory.env
EOF

source ~/.zshrc
```

Verify:
```bash
echo $AGENTMEMORY_SECRET
echo $LITELLM_API_KEY
```

### 9d — Wire OpenCode MCP for agentmemory

Find your OpenCode config file (usually `~/.config/opencode/config.json` or similar).

The current config (already applied) in `~/.config/opencode/opencode.json`:
```json
"agentmemory": {
  "type": "local",
  "command": ["npx", "-y", "@agentmemory/mcp"],
  "env": {
    "AGENTMEMORY_URL": "http://192.168.1.10:3111",
    "AGENTMEMORY_SECRET": "xnch-agentmemory-secret"
  },
  "enabled": true
}
```

The `@agentmemory/mcp` MCP shim translates MCP tool calls into REST API calls to the agentmemory server on gate7.

### 9e — Test connections

```bash
# Test agentmemory API reachability
curl -s http://192.168.1.10:3111/health
# Expected: 200 OK

# Test XNCH via i7
curl -s http://192.168.1.10:30800/health | head -20
```

---

## Phase 10 — End-to-End Verification

### 10a — Create SSH config (optional, for XNCH gateway only)

```bash
# agentmemory no longer needs a tunnel — direct LAN at 192.168.1.10:3111
# XNCH gateway uses NodePort 30800 — also direct LAN
cat >> ~/.ssh/config << 'EOF'
Host gate7
  HostName 192.168.1.10
  User x-nch
  ServerAliveInterval 60
  ServerAliveCountMax 3
EOF
```

### 10b — Add local /etc/hosts (optional)

```bash
sudo cat >> /etc/hosts << 'EOF'
127.0.0.1  xnch.local llm.local langfuse.local nexi.local
EOF

cat /etc/hosts | grep local
```

### 10c — Test services

```bash
# XNCH gateway
curl -H "Host: xnch.local" http://localhost:8080/health

# LiteLLM router
curl -H "Host: llm.local" http://localhost:8080/health

# Nexi product
curl -H "Host: nexi.local" http://localhost:8080/health

# AgentMemory viewer
open http://192.168.1.10:3113/

# AgentMemory API (no tunnel needed)
curl -s http://192.168.1.10:3111/
```

### 10e — Test Claude Code + agentmemory

```bash
# Source env vars and start Claude Code
source ~/.openclaw/claude-code-agentmemory.env
claude

# Inside Claude Code, run:
#   /agentmemory recall "why we chose postgres"
# Should return memories from your xnch-build namespace
```

### 10e — Test OpenCode MCP

```bash
# Start OpenCode
opencode

# Try an MCP tool:
#   Use the agentmemory MCP — should list tools for memory_save, memory_recall etc.
```

### 10g — Test end-to-end with Telegram

1. Open Telegram, find the bot created in Phase 8
2. Send a message: "What's your name?"
3. Watch the flow:
   - Bot receives message
   - Forwards to OpenClaw i7 (systemd)
   - OpenClaw → XNCH (30800) → routes to Nexi
   - Nexi → fetches memory context → calls Gemma4 via LiteLLM
   - Gemma4 (RTX 3090) generates response
   - Response flows back → Telegram
4. Check agentmemory captured it:
   ```bash
   curl -s http://192.168.1.10:3111/agentmemory/search?q=your+name | python3 -m json.tool
   ```
5. Check XnchMemory wrote it:
   ```bash
   sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 \
     "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml && \
      kubectl logs -n xnch-system -l app=xnch --tail=50 | grep -i 'episode\|store'"
   ```

---

## Verification Checklist

| Component | Command | Expected |
|-----------|---------|----------|
| K3s cluster | `kubectl get nodes` | gate7 (Ready) + xnch-core (Ready) |
| XNCH pod | `kubectl get pods -n xnch-system -l app=xnch` | Running |
| Nexi pod | `kubectl get pods -n xnch-system -l app=nexi` | Running |
| Gemma4 service | `sshpass -p xnch ssh x-nch@192.168.1.9 "curl -s http://localhost:8080/v1/models"` | Model list |
| OpenClaw i7 | `sshpass -p xnch ssh x-nch@192.168.1.10 "sudo systemctl status openclaw-i7"` | active (running) |
| AgentMemory API | `curl -s http://192.168.1.10:3111/health` | 200 |
| Traefik routes | `curl -H "Host: xnch.local" http://localhost:8080/health` | 200 |
| AgentMemory viewer | `open http://192.168.1.10:3113/` | Viewer loads |
| Telegram | Send message to bot | Response in < 10 seconds |
| Memory | `curl -s http://192.168.1.10:3111/agentmemory/search?q=test` | Returns memories |

---

## Known Issues & Workarounds

### Zep Pod Broken
**Issue:** zep-deployment Error 14 (tiktoken encoding download timeout).
**Impact:** Zep not extracting entities, but not blocking other services.
**Fix needed:** Pre-download `cl100k_base.tiktoken` encoding or use local embedder model.

### CoreDNS Cross-Node DNS
**Issue:** i9 pods cannot reach i7 services via DNS (UDP port 53 blocked on Flannel overlay).
**Workaround:** hostAliases in nexi pod maps service names to ClusterIPs.
**Impact:** Works but limits DNS flexibility.

### OpenClaw Mac Offline
**Issue:** If your Mac is off, OpenClaw i7 is still online (good for Telegram).
**Design:** By design — i7 is always-on, Mac is interactive.

---

## Next: Troubleshooting

If services don't connect:

```bash
# Check K8s logs
kubectl logs -n xnch-system -l app=nexi --tail=50

# Check XNCH logs
kubectl logs -n xnch-system -l app=xnch --tail=50

# Check OpenClaw i7 logs
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 \
  "sudo journalctl -u openclaw-i7 -n 50 --no-pager"

# Check agentmemory logs
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.10 \
  "sudo journalctl -u agentmemory -n 50 --no-pager"

# Check Gemma4 service on i9
sshpass -p xnch ssh -o StrictHostKeyChecking=no x-nch@192.168.1.9 \
  "sudo systemctl status gemma4-llama --no-pager && \
   nvidia-smi"
```

---

## What You've Built

✅ **K3s Homelab** — 2-node cluster, fully automated, K3s managed.
✅ **XNCH Platform** — Routing, orchestration, memory persistence.
✅ **Nexi Character** — Intent → evaluation → dispatch pipeline.
✅ **Gemma4 Inference** — RTX 3090, 135 tok/s, FP8 quantized.
✅ **Memory Layers** — 4-layer XnchMemory + AgentMemory for coding.
✅ **Always-On Presence** — OpenClaw i7 (Telegram/WhatsApp 24/7).
✅ **Interactive Surface** — OpenClaw Mac + Claude Code + OpenCode.
✅ **Observability** — Langfuse traces + AgentMemory capture.

**Total ownership:** Full stack, no external services except OpenAI API (optional).
