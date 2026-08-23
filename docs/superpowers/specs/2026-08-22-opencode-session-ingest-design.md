# OpenCode Session Ingest — Design

Date: 2026-08-22
Status: Approved (in chat), implementation in progress

## Problem

OpenCode persists agent sessions locally; xnch's four-tier memory has no visibility into
them. We need structured per-session summaries in the episodic tier (Postgres + pgvector)
and durable facts promoted into the semantic tier (Kuzu), traced via Langfuse.

## Storage findings (verified 2026-08-22)

- Primary store: `~/.local/share/opencode/opencode.db` — SQLite (WAL, live).
  - `session(id, project_id, title, directory, agent, model, cost, tokens_*, time_created,
    time_updated, time_archived)` — ms-epoch ints; 682 rows spanning Dec 2025 → Aug 2026.
  - `message(id, session_id, data JSON)` — role, modelID, path.cwd, finish.
  - `part(id, message_id, session_id, data JSON)` — typed parts: `tool` (state.input/output),
    `text`, `reasoning`, `patch`, `file`, `step-start/finish`, `compaction`.
- Legacy JSON storage under `~/.local/share/opencode/storage/` is residual (~2 dirs) — ignored.
- The removed `agentmemory` Python package is NOT involved; repo `.opencode.json` references an
  unrelated external MCP service. No dependency reintroduced.
- Read access: stdlib `sqlite3` in read-only URI mode (`file:...?mode=ro`). Zero new deps.

## Decisions

1. **Bi-temporal**: Kuzu schema extended with `valid_from` / `invalidated_at` (+ `source`) on
   `entities` and `relations`. First writers of the convention are session facts; existing
   callers unaffected (defaults preserve behavior). Note: no such columns existed before —
   this implements the convention first described in misc/rearchitecture-discussion.md:446.
2. **Entry point**: job + CLI mirroring consolidation (`xnch/memory/session_ingest/ingestor.py`
   core, `xnch/jobs/session_ingest.py` scheduler wrapper, `run_session_ingest.py` CLI) with
   `--backfill | --incremental | --session-id | --dry-run | --limit | --since`.
   Incremental scheduling wired into the xnch lifespan APScheduler (hourly at
   `XNCH_SESSION_INGEST_CRON_MINUTE`, default :15; disable with
   `XNCH_SESSION_INGEST_SCHEDULED=false`).
3. **Scope**: project-filtered by default (workspace directories); `--all` overrides.
4. **LLM**: single-pass summarizer via LiteLLM proxy (`openai/ornith`, vLLM node-b) following
   `_extract_litellm` patterns; never routes to external APIs; Langfuse-traced per call.
5. **Redaction**: hard gate before any store write; applied to transcript digest AND LLM output.

## Architecture

```
xnch/memory/session_ingest/
  models.py       SessionDigest (parsed), SessionSummary (LLM output) pydantic models
  parser.py       sqlite3 read-only reader -> SessionDigest
  redactor.py     regex battery -> [REDACTED:<type>], hit counts
  summarizer.py   LiteLLM ornith call -> SessionSummary (JSON, fence-stripped)
  ingestor.py     orchestration + ledger bookkeeping (ingest_sessions, IngestReport)
xnch/jobs/run_session_ingest.py    CLI entrypoint
```

Data flow per session:

```
opencode.db --parser--> SessionDigest --summarizer--> SessionSummary
      \                                                    |
       \-------- redactor(digest) --------+                |
                                          v                v
                          PgEpisodicStore.store_session_episode (redacted raw+summary)
                                          |
                          GraphStore facts (bi-temporal valid_from=session end,
                                            source=opencode:<sid>)
```

- Episode: `type='opencode_session'`, importance 1.5, timestamp = session end time.
- Ledger: `session_ingest_ledger(session_id PK, episode_id UUID, status, facts_count,
  error, ingested_at)` applied idempotently by PgEpisodicStore.connect(). Idempotency:
  SUCCEEDED rows skipped on re-run.
- Facts: same JSON response as summary carries `facts[]` triples; written via extended
  `upsert_relation(..., valid_from, source)`.

## Error handling

- Ornith unreachable / bad JSON → ledger row FAILED with error, run continues, retry next run
  (FAILED rows re-attempted unless `--skip-failed`).
- Parser errors on one session never abort the batch.
- Redaction runs even when summarization fails (digest still stored).
- `--dry-run` connects Postgres (ledger read + idempotent DDL) but NEVER opens Kuzu —
  schema migrations are treated as writes and excluded from dry-run mode.

## Testing

- Fixture SQLite DBs built from real sampled sessions (sanitized) for parser tests.
- ≥8 secret-pattern tests including a realistic pasted OpenAI-style key.
- Idempotency: double ingestion ⇒ exactly one episode (ledger skip).
- Kuzu bi-temporal stamping against a real tmp Kuzu DB.
- Summarizer JSON parsing incl. fenced output and malformed fallback.
- Ordering guarantee: mocked stores assert no un-redacted secret reaches a write call.

## Out of scope (v1)

- Re-ingestion of *updated* sessions (incremental mode covers only previously-unseen sessions;
  `--resync` future work).
- Legacy JSON storage parsing.
- Scheduled wiring (APScheduler/systemd) — post-review.
