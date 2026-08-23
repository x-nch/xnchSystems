# Runbook — GPU Window Protocol (Node B)

The RTX 3090 (24 GiB) currently has exactly one tenant: **vllm-ornith**
(~22 GiB). Training/eval jobs that need the GPU are future phases
([training ADR](../adr/2026-08-22-training-subsystem.md)); until they exist,
handoff is manual.

## Reality check (code wins)

- In-repo systemd units contain **no `Conflicts=` exclusivity group** — only
  ordering deps (`vllm-ornith` After/Wants `nvidia-ready.service`). The ADR's
  "Conflicts= group with Vision Media Stack" is target-state intent, not
  current tree.
- Consequence: nothing stops you starting a second GPU process. Discipline is
  procedural.

## Take window (stop serving)

```bash
ssh x-nch@192.168.50.2
nvidia-smi                                    # confirm only vllm resident
sudo systemctl stop nexi.service              # first: stop decision engine (it calls Ornith)
sudo systemctl stop vllm-ornith.service       # then free VRAM
nvidia-smi                                    # verify 0 processes / memory freed
```

Announce intent + expected duration before stopping — this is a whole-system
inference outage by design.

## Do the work

Run your GPU job in its own venv (never inside xnch/nexi envs).
For dry-run eval only: [run-eval](../guides/run-eval.md) works against a
running server or `--fake-reply` offline mode.

## Release window (resume serving)

```bash
sudo systemctl start vllm-ornith.service
curl -sf http://localhost:8082/health         # wait for model load (~1 min)
sudo systemctl start nexi.service
curl -sf http://localhost:8000/health
# from Node A: ./infra/no-k3s/e2e-test.sh     # full-stack confirmation
```

## Future state (per ADR, not yet built)

Exclusive Train/Promote windows as systemd peers joining a real `Conflicts=`
group; promotion via HITL-approved symlink flip + restart. Track against the
ADR rather than this runbook once implemented.
