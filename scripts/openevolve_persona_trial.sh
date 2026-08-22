#!/usr/bin/env bash
# OpenEvolve trial scaffold for nexi/character/persona.yaml (offline CLI only).
# Prerequisite: loop-2 harness fitness (nexi/eval) must exist — it does.
# Target model: qwen2.5-vl-7b (production resident). Escalate to ornith only if plateau.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR="${WORKDIR:-/tmp/openevolve-persona}"
mkdir -p "$WORKDIR"

cat >"${WORKDIR}/README.md" <<EOF
# OpenEvolve persona trial

1. Install offline (not a runtime dep of xnchSystems):
   pip install openevolve

2. Initial program = copy of:
   ${ROOT}/nexi/character/persona.yaml

3. Evaluator = call nexi.eval harness (deterministic first):
   cd ${ROOT} && .venv/bin/python -m nexi.eval.cli --fixture
   Fitness = pass_rate / mean_score from EvalRunResult.
   Feed grader failures into the next mutation prompt (artifact side-channel).

4. api_base = LiteLLM pointing at resident model (qwen-vl):
   provider opencode-compatible OpenAI base → litellm qwen2.5-vl-7b

5. Budget: 20–50 iterations. Treat +23% HotpotQA claims as targets, not facts.

6. Do NOT add openevolve to pyproject.toml.
EOF

echo "Scaffold written to ${WORKDIR}/README.md"
echo "Harness smoke:"
cd "$ROOT" && .venv/bin/python -m nexi.eval.cli --fixture >/dev/null && echo OK
