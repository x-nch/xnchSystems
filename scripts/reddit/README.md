# xnch Reddit Agent

A **special agent** that posts and DMs on Reddit, built inside the existing
xnch agent-dispatch + HITL architecture. The LLM only *drafts* text; the
trusted `agent-runner` performs the one external, consequential call.

## Components
- `reddit_agent.py` — executor (OAuth2, `post` + `message`, `--dry-run`). The
  only component that touches Reddit.
- `agent-runner` routes runs whose prompt starts with `@reddit` to this executor.

## Setup
1. Create a Reddit app: https://www.reddit.com/prefs/apps → type **script**
   (personal use). Copy its client_id.
2. `cp reddit.env.example ~/.xnch/reddit.env` and fill in client_id / username /
   password. (`~/.xnch/reddit.env` is gitignored by convention; never commit it.)
3. The agent-runner reads creds from that file (or `XNCH_REDDIT_*` env). No
   secrets are passed to the LLM.

## Usage
CLI (dry-run, no network):
```bash
python3 reddit_agent.py post --subreddit r/selfhosted \
  --title "xnchSystems: local-first AI orchestration" --body "..." --dry-run
python3 reddit_agent.py message --to u/someuser --subject "hi" --body "..." --dry-run
```

Dispatch path (HITL-gated): a goal/workflow whose step is a Reddit task files an
**elevated** approval (external action, like `publish`/`send_email`). Admin
approves → `spawn_agent_run_for_approval` creates an `agent_run` whose prompt is
the `@reddit` directive → the runner executes it:
```
@reddit {"action":"post","subreddit":"r/selfhosted","title":"...","body":"..."}
@reddit {"action":"message","to":"u/someuser","subject":"...","body":"..."}
```

## Safety
- External action ⇒ requires the admin approval gate (do not bypass).
- Missing credentials ⇒ executor forces `--dry-run` (validates, no network).
- The sandboxed LLM (`xnch-dispatch`) has no bash/MCP/network, so it cannot call
  Reddit directly — only this trusted executor can.
