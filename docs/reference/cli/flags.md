# CLI Flags

Detailed reference for CLI flags and options.

## Global Flags

These flags work with any command.

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--config` | `-c` | Config file path | `~/.xnch/config.yaml` |
| `--verbose` | `-v` | Enable verbose output | `false` |
| `--quiet` | `-q` | Suppress non-error output | `false` |
| `--no-color` | | Disable colored output | `false` |
| `--help` | `-h` | Show help | |

## Execute Flags

Flags specific to the `execute` command.

| Flag | Description | Default |
|------|-------------|---------|
| `--dry-run` | Simulate without executing | `false` |
| `--show-candidates` | Display all candidate plans | `false` |
| `--require-approval` | Always require human approval | `false` |
| `--output` | Output format (text, json, yaml) | `text` |
| `--timeout` | Execution timeout in seconds | Config default |
| `--env KEY=VALUE` | Set environment variable | |

### Examples

```bash
# Basic execution
xnch execute "Create backup"

# Dry run with candidates
xnch execute "Deploy" --dry-run --show-candidates

# Force approval
xnch execute "Delete logs" --require-approval

# JSON output
xnch execute "Query" --output json

# With environment
xnch execute "Run" --env ENV=production
```

## Serve Flags

Flags specific to the `serve` command.

| Flag | Description | Default |
|------|-------------|---------|
| `--host` | Bind address | `127.0.0.1` |
| `--port` | Bind port | `8000` |
| `--workers` | Number of worker processes | `1` |
| `--reload` | Auto-reload on code changes | `false` |
| `--log-level` | Logging level | Config default |
| `--ssl-cert` | SSL certificate path | |
| `--ssl-key` | SSL key path | |

### Examples

```bash
# Default
xnch serve

# Production
xnch serve --host=0.0.0.0 --port=8000 --workers=4

# Development
xnch serve --reload --log-level=DEBUG
```

## Audit Flags

Flags specific to audit commands.

| Flag | Description |
|------|-------------|
| `--limit` | Number of results |
| `--offset` | Pagination offset |
| `--since` | Filter since time |
| `--until` | Filter until time |
| `--level` | Filter by log level |
| `--format` | Output format (table, json, csv) |

### Examples

```bash
xnch audit decisions --limit=5
xnch audit events --level=ERROR --since=1h
xnch audit search "delete" --since=2024-01-01
```

## Memory Flags

Flags specific to memory commands.

| Flag | Description |
|------|-------------|
| `--store` | Specific store (context, outcome, pattern, vector) |
| `--limit` | Number of results |
| `--format` | Output format |

### Examples

```bash
xnch memory stats
xnch memory search "backup" --limit=10
xnch memory outcomes --store=outcome --limit=20
```

## Learning Flags

Flags specific to learning commands.

| Flag | Description |
|------|-------------|
| `--force` | Force operation |
| `--dry-run` | Show what would happen |
| `--min-confidence` | Filter by confidence |

### Examples

```bash
xnch learning stats
xnch learning extract --force
xnch learning candidates --min-confidence=0.8
```

## Policy Flags

Flags specific to policy commands.

| Flag | Description |
|------|-------------|
| `--format` | Policy file format (yaml, json) |
| `--validate` | Validate only |

### Examples

```bash
xnch policy list
xnch policy validate ./custom.yaml
xnch policy test ./policies.yaml --intent="Delete"
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XNCH_CONFIG` | Config file path |
| `XNCH_DATA_DIR` | Data directory |
| `XNCH_LOG_LEVEL` | Log level |
| `XNCH_NO_COLOR` | Disable colors |
| `XNCH_API_KEY` | API key for remote access |