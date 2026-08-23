# Runbook — Restart Node B services

Node B = xnch-core (`192.168.50.2`), bare venv + systemd, no Docker.
Sources: `infra/no-k3s/node-b/**`.

## vLLM Ornith (:8082)

GPU (~22 GiB of 24) must be idle before start:

```bash
nvidia-smi                                          # confirm no processes
sudo systemctl restart vllm-ornith.service
curl -sf http://localhost:8082/health               # may take ~1min to load model
```

If the GPU is busy, run the [gpu window protocol](gpu-window.md) first.
Unit env pins `VLLM_ATTENTION_BACKEND=FLASH_ATTN`, GPTQ via `gptq_marlin`;
model dir `~/models/ornith-gptq-pro`, venv `~/venvs/vllm-ornith`.

## nexi (:8000)

```bash
sudo systemctl restart nexi.service
curl -sf http://localhost:8000/health
journalctl -u nexi.service -n 50 --no-pager         # on failure
```

Requires Node A reachable (xnch :8001, redis, postgres, litellm) and
`PYTHONPATH` covering both `nexi/` and `xnch/` dirs — both are set in the unit;
do not override casually.

## exec / fs agents (:8004 / :8003)

```bash
sudo systemctl restart exec-agent.service fs-read-agent.service
curl -sf http://localhost:8004/health
curl -sf http://localhost:8003/health
```

Both read `~/.xnch/nexi.env` + policy files; host pinning via
`XNCH_EXEC_LOCAL_HOST=node-b` / `XNCH_FS_LOCAL_HOST=node-b`.

## Full Node B bounce (incl. wake from sleep)

Prefer the scripted path from **Node A**:
`wake-node-b.sh` then `start-node-b.sh --no-wait-node-a`
([wake runbook](wake-node-b.md)). On-node manual:

```bash
sudo systemctl start nvidia-ready.service vllm-ornith.service   # ordering handles deps
sudo systemctl start nexi.service exec-agent.service fs-read-agent.service
```

## After any Node B restart

- Re-check from Node A: `./infra/no-k3s/e2e-test.sh`.
- Workflow executor resumes claiming APPROVED steps automatically within its
  poll interval; stale CLAIMED steps are reclaimed after lease expiry
  ([semantics](../architecture/workflows-hitl.md#executor-claim-lease-semantics-nexiworkflowexecutorpy)).
