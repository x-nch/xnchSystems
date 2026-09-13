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

Requires Node A reachable (xnch :8001, redis, postgres) and
`PYTHONPATH` covering both `nexi/` and `xnch/` dirs — both are set in the unit;
do not override casually.

## capability sidecar (:8090)

```bash
sudo systemctl restart xnch-capability.service
curl -sf http://127.0.0.1:8090/health   # {"status":"ok","capabilities":"exec,fs"}
journalctl -u xnch-capability.service -n 20 --no-pager  # on failure
```

Reads `XNCH_CAPABILITY_TOKEN` from `/home/x-nch/.xnch/nexi.env`. Replaces the legacy sidecar services (exec-agent :8004 + fs-read-agent :8003).

## Full Node B bounce (incl. wake from sleep)

Prefer the scripted path from **Node A**:
`wake-node-b.sh` then `start-node-b.sh --no-wait-node-a`
([wake runbook](wake-node-b.md)). On-node manual:

```bash
sudo systemctl start nvidia-ready.service vllm-ornith.service   # ordering handles deps
sudo systemctl start nexi.service xnch-capability.service
```

## After any Node B restart

- Re-check from Node A: `./infra/no-k3s/e2e-test.sh`.
- Workflow executor resumes claiming APPROVED steps automatically within its
  poll interval; stale CLAIMED steps are reclaimed after lease expiry
  ([semantics](../architecture/workflows-hitl.md#executor-claim-lease-semantics-nexiworkflowexecutorpy)).
- If memory-service on node-a was restarted concurrently, verify Kuzu safety:
  exactly ONE process (embedded gateway XOR memory-service) must own the Kuzu
  file. See [memory-service-deploy.md](memory-service-deploy.md#invariants).
