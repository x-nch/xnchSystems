#!/usr/bin/env bash
# Install Piper voice assets for Nexi TTS on gate7.
set -euo pipefail

VOICE_DIR="${HOME}/.xnch/voice"
VOICE_NAME="en_US-lessac-medium"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

mkdir -p "${VOICE_DIR}"

if [[ ! -f "${VOICE_DIR}/${VOICE_NAME}.onnx" ]]; then
  echo "Downloading ${VOICE_NAME}.onnx..."
  curl -fsSL "${BASE_URL}/${VOICE_NAME}.onnx" -o "${VOICE_DIR}/${VOICE_NAME}.onnx"
fi

if [[ ! -f "${VOICE_DIR}/${VOICE_NAME}.onnx.json" ]]; then
  echo "Downloading ${VOICE_NAME}.onnx.json..."
  curl -fsSL "${BASE_URL}/${VOICE_NAME}.onnx.json" -o "${VOICE_DIR}/${VOICE_NAME}.onnx.json"
fi

echo "Voice models installed under ${VOICE_DIR}"
echo "Ensure 'piper' is in PATH (https://github.com/rhasspy/piper/releases)"
echo "Optional STT: pip install faster-whisper"
