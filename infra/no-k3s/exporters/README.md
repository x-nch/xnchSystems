# Exporters — Node A + Node B metric shims

Plain-metrics exporters scraped by Prometheus (see `../node-a/prometheus/`).
None of these files contain credentials; nothing here authenticates because
all endpoints are LAN-internal (192.168.50.0/24). Do NOT port-forward any of
these through the Tailscale funnel.

## Install on Node A (control plane)

```bash
sudo infra/no-k3s/exporters/install-node-exporter.sh
```

## Install on Node B (GPU)

```bash
sudo infra/no-k3s/exporters/install-node-exporter.sh gpu
sudo infra/no-k3s/exporters/install-dcgm-exporter.sh   # needs docker + nvidia-container-toolkit (script installs toolkit)
```

On Node B the installer enables node_exporter's **systemd collector** limited
to the units that implement the Ornith ↔ Vision Media Stack exclusivity lock.
The lock holder is then derivable in PromQL:

```promql
node_systemd_unit_state{name="vllm-ornith.service",state="active"}
node_systemd_unit_state{name=~".*vision.*media.*",state="active"}
```

If the Vision Media Stack's actual unit name differs, set
`NODE_EXPORTER_UNIT_INCLUDE` when re-running the installer (it writes
`/etc/default/node_exporter`).

## What lands where

| File | Target | Purpose |
|---|---|---|
| `node_exporter.service` | both nodes | host metrics; systemd collector = lock-holder signal |
| `install-node-exporter.sh` | both nodes | fetch pinned binary, write defaults, enable unit |
| `dcgm-exporter.service` | Node B | VRAM/util/temp/power via NVIDIA DCGM |
| `install-dcgm-exporter.sh` | Node B | toolkit bootstrap + unit install |

## Adding a new exporter later

1. Add its systemd unit here (no secrets — use env files on the node if it
   ever needs one).
2. Add a `scrape_configs:` entry in `../node-a/prometheus/prometheus.yml`.
3. Extend `scripts/observability-smoke.sh` so the series shows up in the
   post-deploy check.
