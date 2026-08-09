#!/usr/bin/env bash
# Nexi voice — Mac client bootstrap (mic/speaker local, STT/TTS on gate7).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Nexi voice Mac client setup"
echo "    Repo: $REPO_ROOT"

if ! command -v python3.13 >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.13+ (brew install python@3.13)" >&2
  exit 1
fi

PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if command -v python3.13 >/dev/null 2>&1; then
    PY=python3.13
  else
    PY=python3
  fi
fi

if [[ "$(uname -s)" == "Darwin" ]] && ! brew list portaudio &>/dev/null; then
  echo "==> Installing portaudio (brew)..."
  brew install portaudio
fi

if command -v uv >/dev/null 2>&1; then
  uv venv --python "$PY" .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -e .
  uv pip install sounddevice numpy
else
  "$PY" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -U pip
  pip install -e .
  pip install sounddevice numpy
fi

ENV_FILE="${HOME}/.xnch/xnch.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cat >"$ENV_FILE" <<'EOF'
# Nexi Mac client — edit XNCH_AUTH_SECRET from gate7
export XNCH_BASE_URL=http://192.168.50.1:8001
export NEXI_BASE_URL=http://192.168.50.2:8000
export XNCH_ACTOR=operator
export XNCH_AUTH_SECRET=CHANGE_ME
export XNCH_VOICE_SAMPLE_RATE=16000
EOF
  echo "==> Wrote $ENV_FILE — set XNCH_AUTH_SECRET from gate7"
else
  echo "==> Keeping existing $ENV_FILE"
fi

echo ""
echo "Next:"
echo "  source .venv/bin/activate"
echo "  set -a && source ~/.xnch/xnch.env && set +a"
echo "  curl -sf \"\$XNCH_BASE_URL/health\""
echo "  python -m cli voice devices"
echo "  python -m cli voice talk --once"
echo ""
echo "Full guide: docs/guides/nexi-voice-mac-client.md"
