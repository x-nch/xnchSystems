# Quick Start Guide

---
tags:
  - #guide
  - #reference
---

Get xnch + Nexi running in under 5 minutes.

## Prerequisites

- Python 3.11+
- SQLite 3.35+
- Redis (optional, for KV cache)
- vLLM or Ollama (optional, for local LLM)

## Installation

```bash
pip install xnch-cli
```

## Initial Setup

```bash
xnch init
```

This creates:
- `~/.xnch/config.yaml` - Main configuration
- `~/.xnch/memory/` - Memory layer directories
- `~/.xnch/audit/` - Audit log directory

## First Execution

```bash
xnch execute "Your intent here"
```

## Next Steps

- Configure your [model provider](getting-started/configuration.md#model-providers)
- Set up [memory backends](getting-started/configuration.md#memory)
- Review [CLI commands](reference/cli/commands.md)