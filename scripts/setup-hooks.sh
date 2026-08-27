#!/usr/bin/env bash
set -euo pipefail
# Install the post-commit hook that keeps the code-review-graph fresh.
ROOT="$(git rev-parse --show-toplevel)"
# In a git worktree, $ROOT/.git is a file; the real hooks dir lives under
# the worktree's git dir (or .git for a normal checkout).
HOOKS_DIR="$(git rev-parse --git-dir)/hooks"
mkdir -p "$HOOKS_DIR"
ln -sf "$ROOT/scripts/build-crg.sh" "$HOOKS_DIR/post-commit"
chmod +x "$ROOT/scripts/build-crg.sh"
echo "Installed post-commit hook -> $HOOKS_DIR/post-commit"
