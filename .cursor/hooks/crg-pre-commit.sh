#!/usr/bin/env bash
# Run code-review-graph risk summary before git commit; always allow the command.
# detect-changes --brief prints a human panel (not JSON) — must go to stderr.
set -euo pipefail

input=$(cat)
cmd=$(echo "$input" | jq -r '.command // .tool_input.command // empty')

if [[ "$cmd" == *"git commit"* ]]; then
  if command -v code-review-graph >/dev/null 2>&1; then
    repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    code-review-graph detect-changes --brief --repo "$repo" >&2 || true
  fi
fi

echo '{"permission":"allow"}'
