# Runbook — Deploy Observability Stack (metrics, alerting, dashboards)

Deploys the three-phase observability build merged on master
(metrics in both services · Prometheus + Alertmanager + exporters · muse
dashboards). Based on [restart-node-a](restart-node-a.md) /
[restart-node-b](restart-node-b.md) / [observability README](../observability/README.md).

Pre-req: master with the observability merge is **pushed**; nodes will pull it.
Layering rule from the README applies throughout: this stack is infra/security
metrics — LLM-semantic questions stay in Langfuse.

---

## Node A — gate7 (192.168.50.1, control plane)

### 1. App code + xnch restart

```bash
ssh node-a 'cd ~/xnchSystems \
  && git checkout master && git fetch origin && git merge --ff-only origin/master'
ssh node-a 'cd ~/xnchSystems/xnch && ~/.local/bin/uv sync --dev --no-install-project'
#   ^ new dep: prometheus-client. --no-install-project required:
#     flat-layout hatchling cannot build the project itself (known issue).
ssh node-a 'sudo systemctl restart xnch.service'
```

Verify:
```bash
curl -s http://192.168.50.1:8001/metrics | head -1          # starts "# HELP"
curl -s http://192.168.50.1:8001/system/memory-tier-health  # JSON, tiers present
```
(`/metrics` returns 403 unless client IP ∈ `XNCH_METRICS_ALLOW_CIDRS`,
default localhost + 192.168.50.0/24 — probe *from the node* or a LAN host.)

### 2. Prometheus + Alertmanager containers

```bash
ssh node-a 'cd ~/xnchSystems/infra/no-k3s/node-a && docker compose up -d prometheus alertmanager'
ssh node-a 'cd ~/xnchSystems/infra/no-k3s/node-a && docker compose ps'   # both Up
```

### 3. Node exporter

```bash
ssh node-a 'sudo ~/xnchSystems/infra/no-k3s/exporters/install-node-exporter.sh'
```

---

## Node B — xnch-core (192.168.50.2, GPU)

### 4. nexi code + restart

```bash
ssh node-b 'cd ~/xnchSystems \
  && git checkout master && git fetch origin && git merge --ff-only origin/master'
ssh node-b 'cd ~/xnchSystems/nexi && ~/.local/bin/uv sync --dev --no-install-project'
ssh node-b 'sudo systemctl restart nexi.service'
curl -s http://192.168.50.2:8000/metrics | head -1                  # "# HELP"
```

### 5. Node exporter (+GPU collector flags)

```bash
ssh node-b 'sudo ~/xnchSystems/infra/no-k3s/exporters/install-node-exporter.sh gpu'
```

### 6. DCGM exporter

```bash
ssh node-b 'sudo ~/xnchSystems/infra/no-k3s/exporters/install-dcgm-exporter.sh'
#   installs nvidia-container-toolkit if missing; requires docker.
```

### 7. vllm-ornith — no change, CONFIRM up

```bash
ssh node-b 'systemctl is-active vllm-ornith.service'
curl -s http://192.168.50.2:8082/metrics | head -1   # scrape job `vllm-node-b` target
```
If it is down for any reason: [gpu window protocol](gpu-window.md) before touching it.

---

## Validation gate (run from Node A; both nodes must be reachable)

```bash
~/xnchSystems/scripts/observability-smoke.sh        # exit 0 = series present,
                                                    # targets up, rules loaded,
                                                    # alertmanager healthy
# $PWD must be the repo root on node-a (absolute path avoids surprises), and the
# v2.53 image entrypoint is `prometheus` — override to reach promtool:
docker run --rm --entrypoint=promtool \
  -v /home/x-nch/xnchSystems/infra/no-k3s/node-a/prometheus:/etc/prometheus \
  prom/prometheus:v2.53.0 check rules /etc/prometheus/rules/alerts.yml
# SUCCESS: 13 rules found
curl -s localhost:8001/observability/summary | jq '.available'   # true
```

**Security baseline:** `xnch_hitl_gate_bypass_total == 0`.

```bash
curl -s http://localhost:8001/metrics | grep hitl_gate_bypass
```
If > 0 → **STOP. That is the security signal firing.** Investigate the bypass
source before anything else; do not proceed to dashboards/announcement.

### Web (muse, operator Mac)

```bash
cd web && npm ci && npm run build      # then redeploy per current hosting
```

Check `/observability`, `/observability/hitl`, `/observability/inference`
render with real series. Smoke those three routes in **Firefox specifically**
(chart rendering has historically diverged there). Data source: xnch
`/observability/summary` + `/admin/alerts/recent`; if panels are empty, check
`*_METRICS_ALLOW_CIDRS` includes the Mac's IP.

---

## Rollback

| Piece | Rollback |
|---|---|
| prometheus / alertmanager | additive compose services — `docker compose down prometheus alertmanager` removes cleanly; volumes keep history |
| exporters | systemd units — `disable --now` + remove install dir |
| app-side metrics endpoints | additive routes + one guarded import in `memory/db.py`; revert commit restores prior behavior, no data migration involved |
| alerts delivery | route through `POST /admin/alerts` which 403s non-LAN sources by default; killing alertmanager container silences delivery without touching apps |
| web dashboards | previous build redeploy |

App rollbacks never require DB changes; nothing here migrates state.

## Post-deploy baseline snapshot

Record for future alert-tuning:

```bash
curl -s localhost:8001/metrics | grep -E "hitl_|memory_tier_up" 
curl -s http://192.168.50.2:8000/metrics | grep nexi_pipeline_stage
```
