"""Governed command execution HTTP agent (node-b sidecar for xnch MCP)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from xnch.config import settings as xnch_settings
from xnch_mcp.exec.local import LocalExecBackend
from xnch_mcp.exec.policy import ExecDenied, load_exec_policy

app = FastAPI(title="exec-agent", version="0.1.0")

_LOCAL_HOST = os.environ.get("XNCH_EXEC_LOCAL_HOST", "node-b")


def _policy_path() -> Path:
    path = xnch_settings.exec_policy_path
    if path.is_file():
        return path
    repo_default = Path(__file__).resolve().parents[1] / "infra/no-k3s/shared/exec-policy.yaml"
    return repo_default if repo_default.is_file() else path


_policy = load_exec_policy(_policy_path())
_backend = LocalExecBackend(_policy, _LOCAL_HOST)


def _verify_token(
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    expected = xnch_settings.exec_agent_token
    if not expected:
        # Fail CLOSED: an unconfigured token on a 0.0.0.0-bound exec service
        # must be a loud misconfiguration, never silent open access.
        raise HTTPException(status_code=503, detail="exec-agent token not configured")
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid internal token")


class RunRequest(BaseModel):
    command: str
    cwd: str | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST}


@app.post("/run")
async def run_command(
    body: RunRequest,
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return await _backend.run(body.command, cwd=body.cwd)
    except ExecDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def main() -> None:
    host = os.environ.get("XNCH_EXEC_AGENT_BIND", "127.0.0.1")
    port = int(os.environ.get("XNCH_EXEC_AGENT_PORT", "8004"))
    uvicorn.run("exec_agent.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
