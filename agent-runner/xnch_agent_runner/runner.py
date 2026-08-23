"""xnch agent-runner — claims dispatch tasks from xnch and runs them headless.

Pull model: the runner polls xnch's /agents/dispatch/next with a lease claim,
spawns the configured coding-agent CLI (default: `opencode run -p <prompt>`)
inside an isolated workspace, then reports DONE/FAILED with exit code and
workspace path. Stdlib only — safe to run as a resident launchd service.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

_DEFAULT_URL = "http://192.168.1.10:8001"


@dataclass(frozen=True)
class RunnerConfig:
    gateway_url: str
    gateway_secret: str
    runner_id: str
    agent_command: str
    agent_args: str
    timeout_s: int
    poll_s: int

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "RunnerConfig":
        e = dict(os.environ if env is None else env)
        secret = e.get("XNCH_GATEWAY_SECRET", "")
        if not secret:
            raise SystemExit("XNCH_GATEWAY_SECRET is required")
        return cls(
            gateway_url=e.get("XNCH_GATEWAY_URL", _DEFAULT_URL).rstrip("/"),
            gateway_secret=secret,
            runner_id=e.get("XNCH_RUNNER_ID", os.uname().nodename),
            agent_command=e.get("XNCH_AGENT_COMMAND", "opencode"),
            agent_args=e.get("XNCH_AGENT_ARGS", "run"),
            timeout_s=int(e.get("XNCH_RUNNER_TIMEOUT_S", "1800")),
            poll_s=int(e.get("XNCH_RUNNER_POLL_S", "5")),
        )


def mint_token(secret: str, ttl_s: int = 300) -> str:
    expiry = str(int(time.time()) + ttl_s)
    sig = hmac.new(secret.encode(), expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{sig}"


def post_json(
    url: str, payload: dict[str, Any] | None, secret: str
) -> tuple[int, dict[str, Any]]:
    """POST JSON; returns (status, parsed-body-or-{}). Never raises on HTTP errors."""
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else b"",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Gateway-Token": mint_token(secret),
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urlerror.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {}
    except urlerror.URLError as exc:
        return 0, {"detail": f"connection failed: {exc.reason}"}


def build_command(cfg: RunnerConfig, prompt: str) -> list[str]:
    return (
        shlex.split(cfg.agent_command)
        + shlex.split(cfg.agent_args)
        + ["--", prompt]  # positional message; -- guards leading-dash prompts
    )


def handle_once(cfg: RunnerConfig, spawn=None) -> str:
    """One poll cycle: claim -> execute -> report. Returns a human status word."""
    spawn = spawn or subprocess.run
    status, run = post_json(
        f"{cfg.gateway_url}/agents/dispatch/next",
        {"runner_id": cfg.runner_id, "ttl_s": cfg.timeout_s + 120},
        cfg.gateway_secret,
    )
    if status == 204:
        return "empty"
    if status != 200 or not isinstance(run, dict) or "id" not in run:
        print(f"[runner] claim failed ({status}): {run}", file=sys.stderr)
        return "claim-error"

    run_id = run["id"]
    workspace = Path(run["workspace"]).expanduser()
    outcome_url = f"{cfg.gateway_url}/agents/runs/{run_id}/outcome"
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        proc = spawn(
            build_command(cfg, run["prompt"]),
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=cfg.timeout_s,
        )
        ok = proc.returncode == 0
        payload = {
            "outcome_status": "DONE" if ok else "FAILED",
            "exit_code": proc.returncode,
            "output_path": str(workspace),
            **({} if ok else {"error": (proc.stderr or "")[-2000:]}),
        }
        word = "done" if ok else "failed"
    except Exception as exc:  # noqa: BLE001 — any failure must reach xnch as FAILED
        payload = {"outcome_status": "FAILED", "exit_code": -1, "error": str(exc)[-2000:]}
        word = "failed"

    ostatus, obody = post_json(outcome_url, payload, cfg.gateway_secret)
    if ostatus not in (200,):
        print(f"[runner] outcome rejected ({ostatus}): {obody}", file=sys.stderr)
    print(f"[runner] {run_id[:8]} -> {word}")
    return word


def main() -> None:
    cfg = RunnerConfig.from_env()
    print(f"[runner] {cfg.runner_id} polling {cfg.gateway_url} every {cfg.poll_s}s")
    while True:
        try:
            result = handle_once(cfg)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # keep the loop alive no matter what
            print(f"[runner] cycle error: {exc}", file=sys.stderr)
            result = "empty"
        if result == "empty":
            time.sleep(cfg.poll_s)
