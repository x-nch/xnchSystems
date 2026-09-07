# Reddit special-agent routing (2026-09-07)

The Mac dispatch runner (`agent-runner/xnch_agent_runner/runner.py`) routes any
claimed run whose prompt starts with `@reddit` to the trusted Reddit executor
(`scripts/reddit/reddit_agent.py`) instead of spawning opencode. The sandboxed
LLM only *drafts* text; it never sees Reddit credentials (OAuth2) and cannot
reach the network — the single external, consequential call lives in this
runner hook.

## Trigger

```text
@reddit {"action": "...", ...}   # valid JSON after the @reddit prefix
```

Example task JSON: `{"action":"post","subreddit":"r/foo","title":"...","body":"..."}`.

## Credentials

The runner considers creds present when both `XNCH_REDDIT_CLIENT_ID` and
`XNCH_REDDIT_PASSWORD` env vars are set, **or** `~/.xnch/reddit.env` exists.
Credentials (see `scripts/reddit/reddit.env.example`):

| Variable | Purpose |
|---|---|
| `XNCH_REDDIT_CLIENT_ID` | Reddit script-app client id |
| `XNCH_REDDIT_USERNAME` | Reddit account username |
| `XNCH_REDDIT_PASSWORD` | Reddit account password |
| `XNCH_REDDIT_AGENT` | override path to the executor script (default `<repo>/scripts/reddit/reddit_agent.py`) |

No creds present ⇒ the executor runs `--dry-run` (validates + receipts, **no
network**). Real creds belong only in mac/node env files or `~/.xnch/reddit.env`
(which is gitignored by convention) — never in the repo. Setup: create a Reddit
app (type **script**/personal use) at https://www.reddit.com/prefs/apps.

## Outcome

Reports `POST /agents/runs/{run_id}/outcome` with `DONE|FAILED`, `exit_code`,
and `result_text` (last 20000 chars) or `error` (last 2000). Failed runs and
invalid `@reddit` JSON both land as `FAILED`, never crashing the runner loop.