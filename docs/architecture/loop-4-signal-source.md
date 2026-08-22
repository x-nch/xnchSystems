# Loop-4 signal source

**Decision (2026-08-14):** Episodic PostgreSQL is the canonical improvement signal for loop 4 (pattern extraction, policy candidates, eval harness scores). Langfuse remains write-only diagnostics / human observability — no read-path into harness rewrites.

## Why

- `xnch/learning/pattern_extractor.py` already consumes decision episodes from PG
- Eval harness scores land in `eval_runs` (+ `episodes` type=`eval_run`) via `PgEpisodicStore.store_eval_run`
- Same box as xnch — no extra API hop; structured outcomes (success rates, actor role, context signatures)

## Loop-2 harness

- Package: `nexi/eval/` (frozen `cases.yaml`, deterministic graders, optional LLM-judge)
- Run offline smoke: `.venv/bin/python -m nexi.eval.cli --fixture`
- Pre-selection option scoring stays in `nexi/pipeline/evaluator.py` — different concern
