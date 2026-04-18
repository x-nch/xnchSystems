# xnch CLI

The command-line interface for interacting with xnch + Nexi.

## Overview

The xnch CLI is the primary human entry point to the system. Built with Typer and Rich for a polished terminal experience.

## Installation

```bash
pip install xnch-cli
```

## Commands

### execute

Execute an intent through the full Nexi pipeline.

```bash
xnch execute "Create a backup of the production database"
```

**Options**:
- `--dry-run` - Simulate without executing
- `--show-candidates` - Display all candidate plans
- `--verbose` - Show detailed logging

**Example**:
```bash
xnch execute "Deploy the web application" --show-candidates
```

### init

Initialize xnch configuration and directories.

```bash
xnch init
```

Creates:
- `~/.xnch/config.yaml`
- `~/.xnch/memory/`
- `~/.xnch/audit/`
- `~/.xnch/policies/`

### config

Manage configuration.

```bash
# Validate current config
xnch config validate

# Show config location
xnch config path

# Open config in editor
xnch config edit
```

### doctor

Run system diagnostics.

```bash
xnch doctor
```

Checks:
- Python version
- Required packages
- Database connectivity
- Redis connection
- Configuration validity
- Model endpoint availability

### audit

Access audit logs and decision ledger.

```bash
# View recent decisions
xnch audit decisions --limit=10

# Verify ledger integrity
xnch audit verify

# Replay a decision
xnch audit replay dec_abc123

# Search events
xnch audit events --level=ERROR --since=1h
```

### memory

Manage memory stores.

```bash
# Show memory stats
xnch memory stats

# Search context
xnch memory search "backup database"

# Show recent outcomes
xnch memory outcomes --limit=20
```

### learning

Manage learning system.

```bash
# Trigger pattern extraction
xnch learning extract

# Show learning stats
xnch learning stats

# Review policy candidates
xnch learning review-candidates

# Adjust scores
xnch learning adapt-scores
```

### serve

Start the FastAPI server.

```bash
xnch serve --host=0.0.0.0 --port=8000
```

**Options**:
- `--workers` - Number of worker processes
- `--reload` - Auto-reload on code changes

### version

Show version information.

```bash
xnch --version
```

## Configuration

The CLI reads configuration from `~/.xnch/config.yaml` or the path specified by `XNCH_CONFIG`.

## Output Formatting

The CLI uses Rich for formatted output:

- Tables for structured data
- Progress indicators for long operations
- Syntax highlighting for code
- Colored status indicators

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XNCH_CONFIG` | Config file path |
| `XNCH_DATA_DIR` | Data directory |
| `XNCH_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `XNCH_NO_COLOR` | Disable colored output |