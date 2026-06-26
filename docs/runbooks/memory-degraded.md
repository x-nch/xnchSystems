## Memory Degraded — Learning Loop Silent > 7h

The proactivity engine surfaces this as a priority observation when no learning events are detected for > 7h.

### Check Pattern Extractor

Patterns are stored in SQLite at `~/.xnch/xnch.db` (mounted at `/data/xnch/` in the pod).

```bash
kubectl exec -n xnch-system deploy/xnch -- sqlite3 /data/xnch/xnch.db \
  "SELECT MAX(updated_at) AS last_update, COUNT(*) AS count FROM patterns;"
```

**Expected:** `last_update` < 7h ago. If NULL or > 7h, extractor hasn't run.

### Check Scheduler Logs

```bash
kubectl logs -n xnch-system deploy/xnch --tail=100 | grep -i "pattern_extractor\|score_adapter\|scheduler"
```

**Look for:** drift detection events, weight proposals, pattern extraction completion messages.

If no scheduler logs → APScheduler not firing. Check if the scheduler was initialized:
```bash
kubectl logs -n xnch-system deploy/xnch --tail=30 | grep scheduler
```

### Manual Consolidation Trigger

The daily consolidation runs via CronJob at 02:00.

```bash
# Trigger manually
kubectl create job --from=cronjob/consolidation \
  -n xnch-system manual-consolidation-$(date +%s)

# Wait for completion (5 min timeout)
kubectl wait --for=condition=complete \
  job/manual-consolidation-1715000000 \
  -n xnch-system --timeout=300s

# Check logs
kubectl logs job/manual-consolidation-1715000000 -n xnch-system
```

### Verify Graph Growth

```bash
kubectl exec -n xnch-system deploy/kuzu -- \
  kuzu /data/kuzu -c "MATCH (e) RETURN count(e) AS entity_count;"
```

**Expected:** entity count increases after consolidation. Note the value before and after.

If Kuzu not wired yet (declared in architecture but not operational), skip this check.

### Verify Episodic Decay

```bash
# Archived episodes (decay_score below 0.1 threshold)
kubectl exec -n xnch-system deploy/xnch -- \
  psql "$XNCH_POSTGRES_URL" \
  -c "SELECT COUNT(*) FROM agentmemory_episodes WHERE decay_score < 0.1;"

# Recent episodes with decay
kubectl exec -n xnch-system deploy/xnch -- \
  psql "$XNCH_POSTGRES_URL" \
  -c "SELECT id, decay_score, importance, timestamp \
      FROM agentmemory_episodes \
      ORDER BY timestamp DESC LIMIT 10;"
```

**Expected:** After consolidation, decay_score values should have been recomputed and episodes below threshold archived.

### Restart XNCH If Still Stuck

```bash
kubectl rollout restart -n xnch-system deploy/xnch
```

After restart, verify scheduler fires within 5 min:
```bash
kubectl logs -n xnch-system deploy/xnch --tail=50 | grep scheduler
```

If scheduler remains silent → check APScheduler configuration in `xnch/main.py`. The learning loop is wired via:
- Pattern extractor @ `*/6` hour (every 6h)
- Score adapter @ `*/6:30`
- Policy candidate generator @ `*/6:45`
- Consolidation CronJob @ `0 2 * * *` (daily 02:00)
