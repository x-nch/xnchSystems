# CLI Commands

Complete CLI command reference.

## Global Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Config file path |
| `--verbose` | Enable verbose output |
| `--quiet` | Suppress output |
| `--version` | Show version |

## Commands

### execute

Execute an intent.

```bash
xnch execute "Your intent here" [OPTIONS]
```

**Options**:

| Option | Description |
|--------|-------------|
| `--dry-run` | Simulate without executing |
| `--show-candidates` | Display all candidate plans |
| `--require-approval` | Always require approval |
| `--verbose` | Show detailed logging |
| `--output FORMAT` | Output format (json, text) |

**Examples**:

```bash
xnch execute "Create a backup"
xnch execute "Deploy to production" --dry-run --show-candidates
xnch execute "Delete old logs" --require-approval
```

### init

Initialize xnch configuration.

```bash
xnch init [OPTIONS]
```

**Options**:

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing config |
| `--template NAME` | Use template (default, minimal) |

### config

Manage configuration.

```bash
xnch config [COMMAND] [OPTIONS]
```

**Subcommands**:

- `validate` - Validate configuration
- `path` - Show config file path
- `edit` - Open in editor

**Examples**:

```bash
xnch config validate
xnch config path
xnch config edit
```

### doctor

Run system diagnostics.

```bash
xnch doctor [OPTIONS]
```

**Options**:

| Option | Description |
|--------|-------------|
| `--fix` | Attempt to fix issues |
| `--component NAME` | Check specific component |

### audit

Access audit logs.

```bash
xnch audit [COMMAND] [OPTIONS]
```

**Subcommands**:

- `decisions` - Show recent decisions
- `events` - Show system events
- `verify` - Verify ledger integrity
- `replay` - Replay a decision
- `search` - Search audit logs

**Examples**:

```bash
xnch audit decisions --limit=10
xnch audit verify
xnch audit replay dec_abc123
xnch audit events --level=ERROR --since=1h
```

### memory

Manage memory.

```bash
xnch memory [COMMAND] [OPTIONS]
```

**Subcommands**:

- `stats` - Show memory statistics
- `search` - Search context
- `outcomes` - Show recent outcomes
- `patterns` - Show learned patterns
- `clear` - Clear memory stores

**Examples**:

```bash
xnch memory stats
xnch memory search "backup database"
xnch memory outcomes --limit=20
```

### learning

Manage learning system.

```bash
xnch learning [COMMAND] [OPTIONS]
```

**Subcommands**:

- `stats` - Show learning statistics
- `extract` - Trigger pattern extraction
- `adapt-scores` - Trigger score adaptation
- `candidates` - Review policy candidates
- `patterns` - Show extracted patterns

**Examples**:

```bash
xnch learning stats
xnch learning extract
xnch learning candidates
```

### serve

Start API server.

```bash
xnch serve [OPTIONS]
```

**Options**:

| Option | Description |
|--------|-------------|
| `--host HOST` | Bind host (default: 127.0.0.1) |
| `--port PORT` | Bind port (default: 8000) |
| `--workers N` | Number of workers |
| `--reload` | Auto-reload on changes |

**Example**:

```bash
xnch serve --host=0.0.0.0 --port=8000 --workers=4
```

### model

Manage model configuration.

```bash
xnch model [COMMAND] [OPTIONS]
```

**Subcommands**:

- `test` - Test model connectivity
- `info` - Show model information

**Examples**:

```bash
xnch model test "Hello"
xnch model info
```

### policy

Manage policies.

```bash
xnch policy [COMMAND] [OPTIONS]
```

**Subcommands**:

- `list` - List loaded policies
- `validate` - Validate policy file
- `test` - Test policy against intent
- `reload` - Reload policies

**Examples**:

```bash
xnch policy list
xnch policy validate ./policies.yaml
xnch policy test ./policies.yaml --intent="Delete database"
```

### backup

Manage backups.

```bash
xnch backup [COMMAND] [OPTIONS]
```

**Subcommands**:

- `create` - Create backup
- `list` - List backups
- `restore` - Restore from backup

**Examples**:

```bash
xnch backup create
xnch backup list
xnch backup restore backup_20240115.tar.gz
```

### version

Show version.

```bash
xnch version [--verbose]
```

### help

Show help.

```bash
xnch help [COMMAND]
```