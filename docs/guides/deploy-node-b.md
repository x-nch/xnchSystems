# Deploy Node B (xnch-core — inference + decision)

Audience: ops. Sources: `infra/no-k3s/node-b/**`, MIGRATION.md §2,
[topology](../architecture/topology.md). **No Docker on Node B** — bare venvs +
systemd only.

## Prerequisites

- Static IP `192.168.50.2`; reachable from Node A over the 50.x link.
- NVIDIA driver installed (one-time:
  `sudo infra/no-k3s/node-b/setup-gpu-driver.sh && sudo reboot`).
- `~/.xnch/nexi.env` from `shared/.env.example` with cross-node URLs:

```bash
NEXI_LITELLM_PROXY_URL=http://192.168.50.1:4000/v1
NEXI_XNCH_BASE_URL=http://192.168.50.1:8001
NEXI_REDIS_URL=redis://192.168.50.1:6379/0
NEXI_POSTGRES_URL=postgresql://<user>:<pw>@192.168.50.1:5432/xnch   # placeholder values only
```

- vLLM assets: model dir `~/models/ornith-gptq-pro`, venv `~/venvs/vllm-ornith`
  (vllm 0.24.0). nexi venv at `nexi/.venv`.

## Bring-up

```bash
cd ~/xnchSystems/infra/no-k3s/node-b
./start-node-b.sh --install
```

Flags: `--install`, `--skip-vllm`, `--no-wait-node-a`.

Unit install (exact files):

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-ready.service vllm-ornith.service nexi.service exec-agent.service fs-read-agent.service
```

## Verify

```bash
curl -sf http://localhost:8082/health        # vLLM Ornith
curl -sf http://localhost:8000/health        # nexi
curl -sf http://localhost:8003/health        # fs-read-agent
curl -sf http://localhost:8004/health        # exec-agent
redis-cli -h 192.168.50.1 ping               # reaches Node A redis
pg_isready -h 192.168.50.1 -U xnch           # reaches Node A postgres
curl -sf http://192.168.50.1:4000/health     # litellm via master key
```

## Ops gotchas

- **GPU must be idle before `vllm-ornith` starts** (~22 GiB / 24 GiB). Window
  protocol: [gpu-window](../runbooks/gpu-window.md).
- Unit ordering is `After=/Wants= network-online nvidia-ready` for vLLM;
  there is no `Conflicts=` group in-repo (ADR intent only).
- Required vLLM env in the unit: `VLLM_ATTENTION_BACKEND=FLASH_ATTN`,
  `VLLM_USE_FLASHINFER_SAMPLER=0`, `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=0`;
  GPTQ needs `--quantization gptq_marlin`.
- nexi imports xnch modules (`xnch.observability.langfuse_client`,
  `xnch.routing.classifier`) → unit sets
  `PYTHONPATH=/home/x-nch/xnchSystems/nexi:/home/x-nch/xnchSystems/xnch`.
- Session init requires `system_state_version`/`policy_version` matching xnch's
  `/system/state`, else 409.
- Wake/sleep lifecycle: Node B sleeps when idle; wake from Node A via
  [wake runbook](../runbooks/wake-node-b.md).

## Related

- Restart procedures: [restart-node-b](../runbooks/restart-node-b.md)
- Executor enabling (workflows): [workflows architecture](../architecture/workflows-hitl.md)
