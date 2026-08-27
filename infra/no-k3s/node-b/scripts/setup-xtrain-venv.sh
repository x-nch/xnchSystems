#!/usr/bin/env bash
# Idempotent QLoRA training venv for Ornith customization (Node B, RTX3090).
set -euo pipefail
VENV="${XTRAIN_VENV:-$HOME/venvs/xtrain}"
PINFILE="$VENV/requirements.lock"

if [[ ! -d "$VENV" ]]; then
  python3.13 -m venv "$VENV"
fi

# CUDA 12.1 wheel index for torch (matches the vllm-ornith venv's CUDA toolchain).
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install \
  'torch==2.4.1' 'transformers==4.46.1' 'peft==0.13.2' 'trl==0.11.0' \
  'datasets==3.1.0' 'bitsandbytes==0.44.1' 'auto-gptq==0.7.1' \
  --extra-index-url https://download.pytorch.org/whl/cu121
# Pip freeze into a reproducible pin.
"$VENV/bin/pip" freeze > "$PINFILE"
echo "xtrain venv ready: $VENV (pinfile $PINFILE)"
