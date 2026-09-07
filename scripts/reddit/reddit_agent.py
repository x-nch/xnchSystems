#!/usr/bin/env python3
"""xnch Reddit agent — trusted executor for posting and messaging on Reddit.

Security model
--------------
This is the ONLY component that talks to Reddit. It is invoked by the
agent-runner (a trusted Python process on the Mac), never by the sandboxed
LLM (`xnch-dispatch` denies bash/MCP/network). Credentials live in
`~/.xnch/reddit.env` (or `XNCH_REDDIT_*` env vars) and are NEVER exposed to
the LLM. The LLM's job is to draft the text; this agent performs the one
external, consequential call.

Actions
-------
  post     --subreddit r/foo --title "..." --body "..."
  message  --to u/someone   --subject "..." --body "..."
  execute  --json '{"action":"post","subreddit":"r/foo","title":"...","body":"..."}'

Reddit auth (installed-app / script account)
-------------------------------------------
OAuth2 password grant against https://www.reddit.com/api/v1/access_token using
the app client_id (installed apps have no client_secret). Produces an access
token used as a Bearer header on oauth.reddit.com.

dry-run
-------
`--dry-run` (or missing credentials) performs NO network call. It validates the
task, writes a receipt JSON, and exits 0 — so the full pipeline is testable
without a Reddit account. This is the default when credentials are absent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

_USER_AGENT = "xnchSystems-reddit-agent/0.1 by xnch"


def load_creds() -> dict[str, str]:
    """Read Reddit credentials from XNCH_REDDIT_* env or ~/.xnch/reddit.env."""
    creds = {
        "client_id": os.environ.get("XNCH_REDDIT_CLIENT_ID", ""),
        "username": os.environ.get("XNCH_REDDIT_USERNAME", ""),
        "password": os.environ.get("XNCH_REDDIT_PASSWORD", ""),
    }
    env_file = Path(os.path.expanduser("~/.xnch/reddit.env"))
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().upper()
            if key in ("XNCH_REDDIT_CLIENT_ID", "REDDIT_CLIENT_ID"):
                creds["client_id"] = val.strip().strip('"')
            elif key in ("XNCH_REDDIT_USERNAME", "REDDIT_USERNAME"):
                creds["username"] = val.strip().strip('"')
            elif key in ("XNCH_REDDIT_PASSWORD", "REDDIT_PASSWORD"):
                creds["password"] = val.strip().strip('"')
    return creds


def has_creds(creds: dict[str, str]) -> bool:
    return bool(creds.get("client_id") and creds.get("username") and creds.get("password"))


def get_access_token(creds: dict[str, str]) -> str:
    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        data={
            "grant_type": "password",
            "username": creds["username"],
            "password": creds["password"],
        },
        auth=(creds["client_id"], ""),  # installed apps: empty secret
        headers={"User-Agent": _USER_AGENT},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@dataclass
class Receipt:
    action: str
    ok: bool
    detail: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "ok": self.ok, "detail": self.detail, "data": self.data}


def _validate(task: dict[str, Any]) -> str | None:
    action = task.get("action")
    if action not in ("post", "message"):
        return f"unknown action {action!r} (expected 'post' or 'message')"
    if action == "post":
        if not task.get("subreddit"):
            return "post requires 'subreddit'"
        if not task.get("title"):
            return "post requires 'title'"
    else:  # message
        if not task.get("to"):
            return "message requires 'to'"
        if not task.get("subject"):
            return "message requires 'subject'"
    if not task.get("body"):
        return f"{action} requires 'body'"
    return None


def execute(task: dict[str, Any], dry_run: bool = False) -> Receipt:
    err = _validate(task)
    if err:
        return Receipt(task.get("action", "?"), False, err, task)

    action = task["action"]
    creds = load_creds()
    effective_dry = dry_run or not has_creds(creds)

    if effective_dry:
        return Receipt(
            action,
            True,
            "dry-run: validated, no network call performed",
            {**task, "would_call": _endpoint_for(action)},
        )

    token = get_access_token(creds)
    headers = {"Authorization": f"bearer {token}", "User-Agent": _USER_AGENT}
    if action == "post":
        payload = {
            "kind": "self",
            "sr": task["subreddit"].lstrip("r/").lstrip("/"),
            "title": task["title"],
            "text": task["body"],
            "api_type": "json",
        }
        resp = requests.post(
            "https://oauth.reddit.com/api/submit",
            data=payload,
            headers=headers,
            timeout=30,
        )
    else:  # message (DM / compose)
        payload = {
            "to": task["to"].lstrip("u/"),
            "subject": task["subject"],
            "text": task["body"],
            "api_type": "json",
        }
        resp = requests.post(
            "https://oauth.reddit.com/api/compose",
            data=payload,
            headers=headers,
            timeout=30,
        )
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return Receipt(action, False, f"Reddit API error {exc}", {"status": resp.status_code, "text": resp.text[:500]})
    return Receipt(action, True, "ok", {"status": resp.status_code})


def _endpoint_for(action: str) -> str:
    return "POST /api/submit" if action == "post" else "POST /api/compose"


def _task_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "execute":
        return json.loads(args.json)
    task: dict[str, Any] = {"action": args.command, "body": args.body}
    if args.command == "post":
        task["subreddit"] = args.subreddit
        task["title"] = args.title
    else:
        task["to"] = args.to
        task["subject"] = args.subject
    return task


def main(argv: list[str] | None = None) -> int:
    # --dry-run is offered on every subcommand (argparse only applies parent
    # options before the subcommand, so share it via a parent parser).
    drp = argparse.ArgumentParser(add_help=False)
    drp.add_argument("--dry-run", action="store_true", help="no network; validate + receipt only")
    p = argparse.ArgumentParser(description="xnch Reddit agent executor", parents=[drp])
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("post", parents=[drp], help="submit a self-post to a subreddit")
    pp.add_argument("--subreddit", required=True)
    pp.add_argument("--title", required=True)
    pp.add_argument("--body", required=True)

    pm = sub.add_parser("message", parents=[drp], help="send a DM to a redditor")
    pm.add_argument("--to", required=True)
    pm.add_argument("--subject", required=True)
    pm.add_argument("--body", required=True)

    pe = sub.add_parser("execute", parents=[drp], help="run a task dict from JSON")
    pe.add_argument("--json", required=True)

    args = p.parse_args(argv)
    task = _task_from_args(args)
    receipt = execute(task, dry_run=args.dry_run)
    print(json.dumps(receipt.to_dict(), indent=2))
    return 0 if receipt.ok else 1


if __name__ == "__main__":
    sys.exit(main())
