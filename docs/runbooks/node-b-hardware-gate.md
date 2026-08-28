# Runbook — Node B Hardware-Gated Steps (RTX 3090)

Four steps that **can only run on Node B** (`xnch-core`, IP `192.168.50.2`, single
RTX 3090 / 24 GiB). They are the GPU-gated verification windows from the ornith
Phase 1 training work (Tasks 2 / 3 / 4 / 6). Everything here is a **full
inference outage by design** — starting `xtrain-cycle` or `xtrain-promote` is a
peer in the systemd `Conflicts=` group and will stop `vllm-ornith.service`.

Run all commands as `x-nch` on Node B. Connect with:

```bash
ssh x-nch@192.168.50.2        # or: ssh node-b
```

The training venv is `~/venvs/xtrain` (bootstrapped by
`infra/no-k3s/node-b/scripts/setup-xtrain-venv.sh`, pinfile
`~/venvs/xtrain/requirements.lock`; torch 2.4.1 / transformers 4.46.1 / peft
0.13.2 / trl 0.11.0 / CUDA 12.1). `xnch-train` checkout lives at
`~/xnchSystems/xnch-train` with `PYTHONPATH` set to that dir.

> **THE RULE (vLLM `Conflicts=` constraint):** `vllm-ornith.service` declares
> `Conflicts=xtrain-cycle.service xtrain-promote.service vision-media.service`
> (and both xtrain units declare the reciprocal line). A training/promote window
> **stops** vLLM; a deploy **never** restarts vLLM (`docs/deploy.md`). The
> **only** sanctioned vLLM restart is inside `xnch_train.promote.promote()`
> (`systemctl restart vllm-ornith.service`), reached via the Promote Window.
> Never run `systemctl restart vllm-ornith` by hand except inside the drill
> below, and never while a cycle is live.

## Shared pre-flight (every step)

```bash
ssh x-nch@192.168.50.2
nvidia-smi                                              # confirm current tenant
systemctl is-active vllm-ornith.service nexi.service    # note what is running
```

To **take** the window (stop serving) before any GPU step:

```bash
sudo systemctl stop nexi.service      # first: stop the decision engine (it calls Ornith)
sudo systemctl stop vllm-ornith.service   # then free VRAM
nvidia-smi                            # verify 0 processes / memory freed
```

To **release** the window (resume serving) after the step:

```bash
sudo systemctl start vllm-ornith.service
curl -sf http://localhost:8082/health     # wait ~1 min for model load
sudo systemctl start nexi.service
curl -sf http://localhost:8000/health
```

All four steps stop serving; do them inside an **approved GPU window** and
announce intent + expected duration first.

---

## Step 1 — Task 2 Step 5: real GPU QLoRA SFT + G1 confirmation

LoRA-over-NF4 SFT on the real 3090; resolve **Gate G1** (does the pinned vLLM
hot-serve LoRA-over-`gptq_marlin`? — a conformation check; merge→requant stays
the shippable path either way).

### Preconditions
- GPU window taken (vLLM + nexi stopped).
- Training venv present: `~/venvs/xtrain/bin/python -c "import torch; print(torch.cuda.is_available())"` → `True`.
- Scrubbed dataset dir with a valid `scrub_manifest.json` (training refuses
  manifest-less input — `_validate_manifest` in `xnch_train/train/qlora.py`).
- `XTRAIN_PSEUDONYMIZE_SECRET` set (fail-fast in `config.py`).

### Exact commands (flags from `qlora.py` argparse)
Real GPU run (loads NF4 base, LoRA over `q_proj/k_proj/v_proj/o_proj`, SFT):

```bash
cd ~/xnchSystems/xnch-train
PYTHONPATH=$PWD ~/venvs/xtrain/bin/python -m xnch_train.train.qlora \
  --base <nf4-base> \            # ornith-gptq-pro lineage fp16/NF4 base (name or path)
  --dataset <scrubbed-ds> \      # dir containing scrub_manifest.json + records.jsonl
  --out /home/x-nch/xtrain-runs/run1/adapter
```

> No-GPU path (debug only): `--fake-dataset N` generates N fake records and runs
> `fake=True` (no model load). It does **not** exercise the GPU, so it cannot be
> used to claim G1.

### Expected success / verify
- `nvidia-smi` during the run shows peak VRAM ~21–23 GiB and the python process
  on `cuda:0`.
- Process exits `0`; `--out` contains `adapter/adapter_model.safetensors` +
  `adapter_config.json`; stdout prints metrics `{"train_loss": <float>}`.
- **G1 conformation:** probe whether the pinned vLLM hot-serves LoRA over a
  `gptq_marlin` base. Record the finding in the eval report (no path change):
  - If supported: a future hot-swap adapter path becomes viable; merge→requant
    remains the shipped path this plan implements.
  - If not: merge→requant is mandatory (already the default).
- Document the G1 result in `docs/architecture/training.md` + the eval report.

### Rollback / failure
- OOM or crash: process exits non-zero, no checkpoint is registered (registration
  only happens later in the cycle), GPU is released on exit. Re-take the window
  and lower `--out` batch/epoch load or retry. No production impact (vLLM was
  already stopped for the window).
- After the step, release the window (resume vLLM+nexi).

### Safety
- Must run inside a stopped-vLLM window. The cycle unit itself enforces
  `Conflicts=vllm-ornith.service`; running `qlora.py` directly does **not**
  auto-stop vLLM, so you must stop it manually first or it will OOM-contend.

---

## Step 2 — Task 3 Step 4: `systemd-analyze verify` + crash-safety drill

Validate the 3-way `Conflicts=` lock group and prove a crashed cycle never
wedges the GPU.

### Preconditions
- Approved window; vLLM + nexi stopped (so you can freely start/stop units).
- The three units installed: `vllm-ornith.service`, `xtrain-cycle.service`,
  `xtrain-promote.service` (paths under `infra/no-k3s/node-b/systemd/`).
  `vision-media.service` is a placeholder — confirm its real name on Node B and
  that it carries the reciprocal `Conflicts=` line.

### Exact commands
```bash
# Install / refresh units (copy from repo, then daemon-reload)
sudo cp ~/xnchSystems/infra/no-k3s/node-b/systemd/{vllm-ornith,xtrain-cycle,xtrain-promote}.service /etc/systemd/system/
sudo systemctl daemon-reload

# Verify all three parse cleanly
systemd-analyze verify /etc/systemd/system/vllm-ornith.service
systemd-analyze verify /etc/systemd/system/xtrain-cycle.service
systemd-analyze verify /etc/systemd/system/xtrain-promote.service

# Assert pairwise Conflicts group
for u in vllm-ornith xtrain-cycle xtrain-promote; do
  echo "== $u =="; systemctl show -p Conflicts "$u.service"
done
```

### Crash-safety drill
```bash
# (A) Starting a cycle while vLLM is active must NOT silently coexist:
sudo systemctl start vllm-ornith.service
sudo systemctl start xtrain-cycle@run1.service    # Conflicts => systemd stops vllm-ornith
systemctl is-active vllm-ornith.service           # expect: inactive (stopped by conflict)

# (B) Simulate a crashed trainer: SIGKILL the cycle, confirm GPU frees
CY=$(pgrep -f 'xnch_train.train.cycle'); sudo kill -9 "$CY"
nvidia-smi                                          # expect 0 GPU processes
sudo systemctl start vllm-ornith.service            # must restore serving
curl -sf http://localhost:8082/health
```

### Expected success / verify
- `systemd-analyze verify` exits 0 for all three (no `[.*]` complaints).
- Each unit's `Conflicts=` lists the other two xtrain/vllm units.
- (A) starting the cycle while vLLM runs transitions vLLM to `inactive`
  (exclusivity holds). (B) after SIGKILL, `nvidia-smi` shows no process and
  `vllm-ornith` restarts cleanly.

### Rollback / failure
- If a unit fails verify, fix the unit file and re-copy; do not proceed with live
  cycles until `verify` is clean.
- If vLLM won't restart after a crash: check `journalctl -u vllm-ornith` for the
  cause, free the GPU (`nvidia-smi` / `sudo fuser -k /dev/nvidia*`), then
  `systemctl start vllm-ornith`.

### Safety
- **Never start `xtrain-cycle` while vLLM is meant to stay up** outside an
  approved window — `Conflicts=` will kill production inference. The unit is
  `Type=oneshot`, `Restart=no`, `TimeoutStartSec=14400`, so a wedged trainer
  cannot loop; on exit the GPU lock releases and the post-flight
  `xtrain-restart-vllm.sh` restores serving.

---

## Step 3 — Task 4 Step 5: real GPTQ requant + G2 recipe verification + throughput gate

Merge the LoRA adapter into the fp16 base, requantize to GPTQ (`gptq_marlin`),
verify **Gate G2**, and pass the **gate #5 throughput/serving** contract.

### Preconditions
- GPU window taken.
- Adapter dir from Step 1 (`/home/x-nch/xtrain-runs/run1/adapter`) and the fp16
  base available.
- `merge_and_requant(..., fake=False)` is the real GPU path in
  `xnch_train/train/merge.py` (lazy `torch`/`peft`/`auto_gptq` imports).

### Exact commands (real path; function signature from `merge.py`)
```bash
cd ~/xnchSystems/xnch-train
PYTHONPATH=$PWD ~/venvs/xtrain/bin/python - <<'PY'
from pathlib import Path
from xnch_train.train.merge import merge_and_requant
merge_and_requant(
    adapter_dir=Path("/home/x-nch/xtrain-runs/run1/adapter"),
    base_model="<fp16-base>",                       # ornith-gptq-pro fp16 lineage
    out_dir=Path("/home/x-nch/xtrain-runs/run1/merged"),
    fake=False,                                      # real GPU merge + GPTQ requant
)
PY
```
The requant recipe (when the original Ornith recipe is unrecoverable) is the
documented default in `merge._requant_gptq_marlin`:
`bits=4, group_size=128, desc_act=False, damp_percent=0.01`,
`--quantization gptq_marlin`.

### Expected success / verify (G2 + gate #5)
- `out_dir` contains the merged fp16 `*.safetensors` then the requantized
  GPTQ-marlin model (directly loadable by `vllm-ornith.service`).
- **G2:** confirm whether the original Ornith GPTQ-Pro recipe (toolchain +
  calibration set) is recoverable. If **not**, accept the gate-#5 (+10% serving)
  contract and use the documented default recipe above; **record the deviation in
  the eval report** (per ADR OQ5).
- **Gate #5 (throughput/serving):** serve the requantized dir with the same flags
  as `vllm-ornith.service` and bench against the incumbent:
  ```bash
  ~/venvs/vllm-ornith/bin/vllm serve /home/x-nch/xtrain-runs/run1/merged \
    --served-model-name ornith-1.0-35b --host 0.0.0.0 --port 8082 \
    --trust-remote-code --dtype float16 --max-model-len 32768 \
    --quantization gptq_marlin --gpu-memory-utilization 0.95 \
    --enable-prefix-caching --max-num-seqs 2 \
    --enable-auto-tool-choice --tool-call-parser qwen3_xml
  ```
  Then run the fixed-prompt serving bench (Phase 0 `baseline` harness or a
  representative load) and assert **TTFT / p95 latency within +10% of the
  incumbent** (`XTRAIN_SERVING_REGRESSION_BOUND_PCT=10`). Watch GPU throughput
  via `dcgm-exporter.service` (`infra/no-k3s/exporters/`) / vLLM `/metrics`.

### Rollback / failure
- Requant OOM/error: nothing is registered yet (registry write happens in the
  cycle, Step 4); just retry with a smaller calibration batch or free the GPU.
- If gate #5 fails (> +10% regression): **do not promote**. Discard the
  checkpoint, note the variance (expected per ADR §5), and re-tune requant
  params. No production impact — vLLM was stopped for the window.

### Safety
- Must be inside a stopped-vLLM window (same `Conflicts=` rule). The merged dir
  is a derived secret — keep it on Node B NVMe; export only through the HITL gate
  + scrub-manifest audit.

---

## Step 4 — Task 6 Step 5: full Train→Promote→rollback drill (live vLLM restart + Langfuse)

End-to-end cycle on synthetic data, then the **only** sanctioned live vLLM
restart via the Promote Window, plus a rollback flip — emitting Langfuse events.

### Preconditions
- An **approved Goal** claimed for the run (cycles are Goal-gated; `XTRAIN_AUTONOMOUS=false` default → manual).
- GPU window taken (vLLM + nexi stopped) for the **Train** half; the **Promote**
  half *itself* restarts vLLM, so do not pre-start it.
- Registry DB + `~/models/current` symlink target dirs exist (defaults in
  `promote.py`: `~/models/registry.sqlite`, `~/models/current`).
- Langfuse sink configured (`XTRAIN_LANGFUSE_*`) if you want the trace/event
  assertions.

### Exact commands (flags from `cli.py` typer app)
```bash
cd ~/xnchSystems/xnch-train
export PYTHONPATH=$PWD
# 1) TRAIN half — runs end-to-end (extract→scrub→train→merge→requant→eval→propose),
#    but here train is fake-free only inside the cycle's own orchestration; the
#    GPU-backed train/merge from Steps 1-3 already produced the artifact.
#    Drive the cycle as the unit would (run_id = %i, e.g. run1):
~/venvs/xtrain/bin/python -m xnch_train.train.cycle run1 \
  --base <nf4-base> --dataset <scrubbed-synthetic-ds> --out /home/x-nch/xtrain-runs/run1
#   (or the typer CLI: uv run xtrain cycle --out ... --base ... --dataset ...)

# 2) Inspect the eval report (five gate metrics + eligibility verdict):
cat /home/x-nch/xtrain-runs/run1/report.json

# 3) PROMOTE — flips ~/models/current symlink, restarts vLLM, runs smoke.
#    This is the ONLY sanctioned vLLM restart. Use the typer CLI (takes a ckpt id):
uv run xtrain promote <checkpoint_id>        # ckpt id = ckpt-<date>-<goal_id|manual>
#   (the cycle emits ckpt id as f"ckpt-{date}-{goal_id or 'manual'}")
```

> **Unit/scripts footgun:** `xtrain-promote.service` `ExecStart` currently calls
> `python -m xnch_train.promote %i` (a `run_id` positional) whereas
> `promote.promote(checkpoint_id=...)` expects a checkpoint id and the typer CLI
> `xtrain promote <ckpt-id>` is the grounded interface. Use `xtrain promote
> <ckpt-id>` (or call `promote.promote("<ckpt-id>")` directly). Align the unit
> before relying on `systemctl start xtrain-promote@<id>`.

### Expected success / verify
- Cycle exits 0; `report.json` shows all five gate metrics
  (`action_fidelity`, `rejection_avoidance`, `persona_consistency`,
  `tool_call_validity`, serving regression) and an eligibility verdict.
- Promote: `readlink ~/models/current` points at the new merged dir; vLLM comes
  back (`curl -sf http://localhost:8082/health`); smoke passes.
- **Rollback drill:** promote the previous checkpoint id; `readlink
  ~/models/current` flips back and a fresh smoke passes (serving restored to
  incumbent). On any smoke failure `promote.promote` flips the symlink back to
  `prior` automatically and raises.
- **Langfuse:** one `xtrain.cycle` trace (step spans) + a `promotion` and/or
  `rollback` event (via `GoalClient` → xnch `/goals`, `/policy/verdict`, plus
  `observability.CycleTracer` if Task 7 is wired).

### Rollback / failure
- Promote smoke fails → symlink auto-rolls back to `prior`; check
  `journalctl -u xtrain-promote` / the Langfuse `rollback` event.
- If you promoted the wrong checkpoint, just `uv run xtrain promote <prev-ckpt-id>`
  to flip back.
- After the drill, release the window (ensure vLLM + nexi `active`).

### Safety
- **The vLLM restart inside `promote()` is the ONLY permitted vLLM restart.** Do
  not `systemctl restart vllm-ornith` manually and never during a normal deploy
  (`docs/deploy.md`). The Promote unit is `Conflicts=` with vLLM, so launching it
  stops vLLM first; run it only inside an approved window and only after a
  HITL-approved promotion proposal exists.
- `Restart=no` + `TimeoutStartSec=3600` on the promote unit means a failed
  promote stays failed (no loop) and the GPU/symlink state is left for you to
  inspect and roll back.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `qlora.py`: `error: --dataset is required` | Real GPU run needs `--dataset <dir>`; `--fake-dataset N` is the no-GPU path. |
| `ValueError: dataset ... has no scrub_manifest.json` | Training refuses unscrubbed data; run `xtrain validate-dataset <dir>` first (needs `XTRAIN_PSEUDONYMIZE_SECRET`). |
| `systemd-analyze verify` prints `[.*]` warnings | Fix the cited unit; do not run live cycles until clean. |
| Conflicts not enforced (two GPU units both `active`?) | Confirm reciprocal `Conflicts=` lines exist on **all** three units + `vision-media.service`; `daemon-reload` after edits. |
| vLLM won't restart post-crash | `nvidia-smi` / `sudo fuser -k /dev/nvidia*` to free, then `systemctl start vllm-ornith`; check `journalctl -u vllm-ornith`. |
| Gate #5 fails (> +10% p95 regression) | Do **not** promote; re-tune requant (`merge._requant_gptq_marlin` recipe) and re-bench. |
| `xtrain promote` restarts vLLM unexpectedly | Expected — that is the sanctioned restart; ensure you're in an approved window and a proposal exists. |
| Promote unit `python -m xnch_train.promote %i` errors | Use the typer CLI `xtrain promote <ckpt-id>`; align the unit's `ExecStart` (see Step 4 footgun). |
| Langfuse shows no cycle trace | Verify `XTRAIN_LANGFUSE_*`; Task 7 `CycleTracer` must be wired (optional). |

## References
- `docs/deploy.md` — vLLM `Conflicts=` "never restart vllm as part of deploys" rule.
- `docs/runbooks/gpu-window.md` — manual take/release window protocol (pre-Phase-1; Phase 1 makes it systemd-enforced).
- `infra/no-k3s/node-b/systemd/{vllm-ornith,xtrain-cycle,xtrain-promote}.service` — unit files + `Conflicts=` wiring.
- `xnch-train/xnch_train/train/{qlora,merge,registry,cycle,promote,goal}.py` — grounded command/flag sources.
- `docs/superpowers/plans/2026-08-27-customize-ornith-phase1.md` — Tasks 2/3/4/6 source of the four steps + Gates G1/G2.
- `docs/adr/2026-08-22-training-subsystem.md` — gate #5 (+10% serving) contract, ADR §3/§5.
