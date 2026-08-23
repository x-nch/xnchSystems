# Run Eval & Baselines (`xnch-train`)

Audience: operator of eval runs. Sources: `xnch-train/xnch_train/cli.py` (flags
verified against source), [training architecture](../architecture/training.md).
All commands require `XTRAIN_PSEUDONYMIZE_SECRET` to be set.

## 0. Environment

```bash
export XTRAIN_PSEUDONYMIZE_SECRET='<secret>'        # placeholder — required, fail-fast
# optional:
export XTRAIN_POSTGRES_URL='postgresql://<user>:<pw>@localhost:5432/xnch'
export XTRAIN_LANGFUSE_HOST='http://192.168.50.1:3000'
export XTRAIN_LANGFUSE_PUBLIC_KEY='<pk>'
export XTRAIN_LANGFUSE_SECRET_KEY='<sk>'
```

## 1. Extract & scrub a dataset

Commands run inside the package (`cd xnch-train`; self-contained env):

```bash
uv run xtrain extract --out ./datasets/run-2026-08-23 \
  [--pg-dsn postgresql://...] [--skip-langfuse]
# -> "wrote N scrubbed records to ...; counts={...}"
```

Pipeline: PG outcomes+corrections (and Langfuse verdict traces unless skipped)
→ HMAC pseudonymizing scrubber → signed manifest → atomic write. **Nothing raw
touches disk.**

## 2. Gate-check the dataset

```bash
uv run xtrain validate-dataset ./datasets/run-2026-08-23
# exit 0 = valid manifest sign-off; exit 1 = unusable
```

A dataset without a valid scrub manifest is rejected — this is the Phase 0
gate.

## 3. Author a starter suite

```bash
uv run xtrain suite --out ./suites/starter.json [--cutoff 2026-08-01]
```

Writes suite JSON with the persona battery populated; behavioral case lists
stay empty until Phase 2 data exists. Temporal split uses `--cutoff`.

## 4. Capture a baseline

Against live vLLM:

```bash
uv run xtrain baseline \
  --base-url http://192.168.50.2:8082/v1 \
  --model ornith-1.0-35b \
  --suite ./suites/starter.json \
  --out ./reports/incumbent.json \
  [--checkpoint-id incumbent]
```

Offline drill: add `--fake-reply '<text>'` to use the canned client.

The report contains the **five gate metrics** compared later against candidate
checkpoints; tolerance knobs: `XTRAIN_GATE_EPSILON` (0.02),
`XTRAIN_SERVING_REGRESSION_BOUND_PCT` (10).

## What this is NOT (Phase 0)

No fine-tune happens here; the promotion gate is dry-run-only and any future
promotion must ride HITL ([ADR](../adr/2026-08-22-training-subsystem.md),
[gpu-window](../runbooks/gpu-window.md)).
