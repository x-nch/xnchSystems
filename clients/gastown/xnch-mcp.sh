#!/usr/bin/env bash
set -euo pipefail
cd /home/x-nch/xnchSystems
exec ./.venv/bin/python -m xnch_mcp "$@"
