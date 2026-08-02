## Injection Alert — Injection Attempt Detected

### Locate the Event

**Via pod logs:**
```bash
kubectl logs -n xnch-system deploy/xnch --tail=200 | grep injection_attempt
```

**Via event log file** (inside pod at `~/.xnch/audit/events.jsonl`):
```bash
kubectl exec -n xnch-system deploy/xnch -- tail -50 /data/xnch/audit/events.jsonl | grep injection_attempt
```

**Via Langfuse** — filter traces for `injection_guard` component, look for `injection_attempt` event type.

**Expected output per event:**
```
timestamp: 2026-06-27T12:00:00Z
component: injection_guard
event_type: injection_attempt
data.matched_patterns: ["ignore previous instructions"]
data.risk_score: 0.11
data.text_preview: "ignore previous instructions and..."
```

### Identify the Matched Pattern

Cross-reference the `matched_patterns` field against `INJECTION_PATTERNS` in `xnch/security/injection_guard.py` (inside xnch submodule):

| Pattern | Regex | Likely Attack |
|---------|-------|--------------|
| 1 | `ignore previous instructions` | Prompt override |
| 2 | `forget your (system prompt\|character\|identity)` | Prompt override |
| 3 | `you are now` | Role re-assignment |
| 4 | `your new (instructions\|role\|persona)` | Role re-assignment |
| 5 | `disregard.*above` | Instruction disregard |
| 6 | `act as (?!Nexi\|nexi)` | Impersonation |
| 7 | `jailbreak` | Explicit jailbreak |
| 8 | `DAN mode` | DAN mode injection |
| 9 | `pretend (you\|that)` | Roleplay exploit |

### Act Based on Actor Role

**If EXTERNAL_AGENT (trust=2):**
- Offending JWT exists (audit event will have `data.trace_id`). Block it:
  ```bash
  # Get jti from event_log trace, add to JTI blacklist
  kubectl exec -n xnch-system deploy/xnch -- sqlite3 /data/xnch/xnch.db \
    "INSERT INTO jti_blacklist (jti, blocked_at) VALUES ('<jti-from-event>', $(date +%s));"
  ```
- Check quarantine store for poisoned memories:
  ```bash
  psql $XNCH_POSTGRES_URL -c "SELECT id, raw_text, quarantine_reason \
    FROM quarantine_memories WHERE released_at IS NULL;"
  ```
- Release false positive:
  ```bash
  psql $XNCH_POSTGRES_URL -c "UPDATE quarantine_memories \
    SET released_at = NOW(), released_by = 'ck-san' \
    WHERE id = '<id>';"
  ```
- If confirmed poison, delete from quarantine AND review `agentmemory_episodes` for affected rows:
  ```bash
  psql $XNCH_POSTGRES_URL -c "DELETE FROM quarantine_memories WHERE id = '<id>';"
  psql $XNCH_POSTGRES_URL -c "SELECT id, raw_text FROM agentmemory_episodes \
    WHERE raw_text ILIKE '%<malicious content>%';"
  ```

**If TRUSTED_AGENT (trust=3):**
More concerning — a trusted component was hijacked or is sending malicious input.

1. Identify which agent: `perception_daemon`, `consolidation_job`, or `opencode`
2. Check the agent's input source:
   - **opencode**: Review the user prompt that was given to it
   - **perception_daemon**: Check if voice transcription was manipulated (see `perception:voice:*` keys in Redis)
   - **consolidation_job**: Check `graph_extractor` output for LLM hallucination
3. Quarantine affected episodes:
   ```bash
   psql $XNCH_POSTGRES_URL -c "INSERT INTO quarantine_memories (id, memory_type, raw_text, summary, quarantine_reason, quarantined_by, original_actor_role, original_trust_level) SELECT gen_random_uuid(), 'episode', raw_text, summary, 'trusted_agent injection', 'ck-san', '<agent_role>', 'TRUSTED_AGENT' FROM agentmemory_episodes WHERE timestamp > '<event_timestamp>';"
   ```

**If OWNER/SYSTEM (trust=4-5):**
- `scan_input()` runs before the trust check in `validate_memory_write()`
- The request was already blocked — no action needed
- `X-Actor-Role` was likely spoofed. Investigate who sent a claim of `operator` or `nexi`:
  ```bash
  kubectl logs -n xnch-system deploy/xnch --tail=500 | grep "X-Actor-Role: operator"
  ```

### Post-Incident

1. If the matched pattern is a legitimate use case, add it to an allowlist check (not yet implemented — file an issue)
2. If a new attack vector was discovered, add a new pattern to `INJECTION_PATTERNS` in `injection_guard.py`
3. Log resolution in incident tracker
