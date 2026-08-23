#!/bin/zsh
# MCP config security scan (2026-08-24 audit U2).
# Scans MCP server configs for tool-poisoning / rug-pull / cross-origin issues.
# Requires SNYK_TOKEN since the Invariant mcp-scan project became Snyk
# Agent Scan (token-gated); skips loudly otherwise.

if ! command -v uvx >/dev/null 2>&1; then
  print -u2 "WARNING: uvx not installed — cannot run agent-scan."
  exit 0
fi

if [ -z "$SNYK_TOKEN" ]; then
  print -u2 "SKIP: SNYK_TOKEN not set — MCP config scan unavailable."
  print -u2 "      Get a token at https://app.snyk.io/account then re-run:"
  print -u2 "      SNYK_TOKEN=<tok> uvx snyk-agent-scan@latest scan ~/.config/opencode/opencode.json"
  exit 0
fi

exec uvx snyk-agent-scan@latest scan "$@"
