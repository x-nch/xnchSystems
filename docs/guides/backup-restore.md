# Backup and Restore

---
tags:
  - #guide
  - #data
---

Data backup and restore procedures.

## What to Backup

### Data Directories

```
~/.xnch/
├── config.yaml          # Configuration
├── memory/              # Memory stores
│   ├── context.db       # Context store
│   ├── outcomes.db      # Outcome store
│   ├── patterns.db      # Pattern store
│   ├── episodic.db      # Episodic store
│   └── vectors/         # Vector store
├── audit/               # Audit logs
│   ├── events.jsonl     # Event log
│   └── decisions.jsonl # Decision ledger
└── policies/            # Policy definitions
```

### Recommendation

| Component | Priority | Frequency |
|-----------|----------|-----------|
| Memory stores | High | Daily |
| Audit logs | Medium | Weekly |
| Config | High | On change |
| Policies | High | On change |

## Manual Backup

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR=~/.xnch/backups
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup SQLite databases
for db in context outcomes patterns episodic; do
    cp ~/.xnch/memory/${db}.db $BACKUP_DIR/${db}_${DATE}.db
done

# Backup audit logs
cp ~/.xnch/audit/events.jsonl $BACKUP_DIR/events_${DATE}.jsonl
cp ~/.xnch/audit/decisions.jsonl $BACKUP_DIR/decisions_${DATE}.jsonl

# Compress
cd $BACKUP_DIR
tar -czf xnch_backup_${DATE}.tar.gz *.db *.jsonl

# Clean up individual files
rm -f *.db *.jsonl

echo "Backup complete: xnch_backup_${DATE}.tar.gz"
```

### Using xnch CLI

```bash
# Create backup
xnch backup create

# List backups
xnch backup list

# Restore from backup
xnch backup restore xnch_backup_20240115_103000.tar.gz
```

## Automated Backup

### Cron Schedule

```bash
# Add to crontab
0 2 * * * xnch backup create --retention=7
```

### Configuration

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention: 7           # Keep 7 backups
  location: ~/.xnch/backups
```

## Restore Procedure

### Full Restore

```bash
# Stop xnch services
xnch serve stop

# Restore from backup
xnch backup restore backup_20240115.tar.gz

# Verify
xnch doctor

# Start services
xnch serve start
```

### Partial Restore

Restore specific stores:

```bash
# Restore only context store
xnch backup restore --store=context backup.tar.gz

# Restore only audit logs
xnch backup restore --store=audit backup.tar.gz
```

## Disaster Recovery

### Recovery Time Objective (RTO)

- Configuration: Immediate
- Memory (last 24h): ~5 minutes
- Full restore: ~15 minutes

### Recovery Point Objective (RPO)

- Daily backups: 24 hours max data loss
- With continuous WAL backup: ~1 minute

### Continuous Backup (SQLite)

```yaml
memory:
  context_store:
    wal_mode: true
    backup:
      enabled: true
      interval: 3600  # Every hour
```

## Migration

### Moving to New Machine

1. Create backup on source:

```bash
xnch backup create --output ~/xnch_backup.tar.gz
```

2. Transfer to new machine:

```bash
scp ~/xnch_backup.tar.gz new-machine:~/
```

3. Restore:

```bash
xnch backup restore ~/xnch_backup.tar.gz
```