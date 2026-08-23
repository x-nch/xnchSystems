# xnch-train

Local training data pipeline + eval harness for the xnchSystems platform.
**Phase 0 scope: extraction → scrubbing → dataset authoring → evaluation →
dry-run promotion gate.** No weight training, and nothing is promoted without
human approval through the platform HITL path.

Design record (immutable): [`docs/adr/2026-08-22-training-subsystem.md`](../docs/adr/2026-08-22-training-subsystem.md) ·
operating docs: [`docs/architecture/training.md`](../docs/architecture/training.md).

## Pipeline

```
Langfuse traces ─┐
Postgres episodes ─┴→ extract → scrub (HMAC pseudonymize) → atomic dataset
                      + signed manifest → validate-dataset gate
                      → eval harness (qwen3_xml · 5 gate metrics · temporal split)
                      → promotion_gate (DRY-RUN report only)
```

Nothing raw touches disk: the scrubber pseudonymizes entities with a
deterministic HMAC key before any write, and datasets are unusable without a
valid manifest sign-off.

## Install & run

```bash
uv sync                       # from repo root; Python 3.13+
export XTRAIN_PSEUDONYMIZE_SECRET='<secret>'   # required — fail-fast when empty

uv run xtrain --help
uv run xtrain extract --out ./datasets/run1 [--pg-dsn DSN] [--skip-langfuse]
uv run xtrain validate-dataset ./datasets/run1      # exit 0 = usable
uv run xtrain suite --out ./suites/starter.json [--cutoff ISO-DATE]
uv run xtrain baseline --base-url http://192.168.50.2:8082/v1 \
    --model ornith-1.0-35b --suite ./suites/starter.json \
    --out ./reports/incumbent.json [--fake-reply TEXT]   # offline drill
```

Full walkthrough: [`docs/guides/run-eval.md`](../docs/guides/run-eval.md).

## Configuration (`XTRAIN_*`)

| Variable | Purpose |
|---|---|
| `XTRAIN_PSEUDONYMIZE_SECRET` | **required**; key for entity pseudonymization + manifest sign-off |
| `XTRAIN_DATASET_DIR` | dataset home (default `./datasets`) |
| `XTRAIN_POSTGRES_URL` | outcome/correction extraction source |
| `XTRAIN_LANGFUSE_HOST/_PUBLIC_KEY/_SECRET_KEY` | trace extraction |
| `XTRAIN_GATE_EPSILON` | gate metric tolerance (0.02) |
| `XTRAIN_SERVING_REGRESSION_BOUND_PCT` | max serving regression (10%) |
| `XTRAIN_EXTRACT_PAGE_SIZE` | extraction pagination (100) |

Exhaustive reference: [`docs/reference/env-vars.md`](../docs/reference/env-vars.md#xtrain_).

## Layout

```
xnch_train/
├── cli.py            # typer app: extract · validate-dataset · suite · baseline
├── config.py         # XTRAIN_ settings (fail-fast secret guard)
├── extract/          # langfuse_extract · pg_extract · dataset_writer
├── scrub/            # scrubber · patterns · pseudonymize
├── models/           # records · manifest (sign-off verification)
├── evalharness/      # client · qwen3xml parser · metrics · suites · runner
└── gate/             # promotion_gate (dry-run)
tests/                # unit suite incl. gate boundaries
```

## What Phase 0 is NOT

No QLoRA/SFT/DPO, no checkpoint merges, no serving changes. Future phases
(adapter training in an isolated Node B venv, exclusive GPU windows, HITL-gated
checkpoint promotion) are specified in the ADR — track there, not here.
