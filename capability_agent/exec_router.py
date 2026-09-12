"""Governed command execution router (capability sidecar, node-b)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from xnch.config import settings as xnch_settings
from xnch_mcp.exec.local import LocalExecBackend
from xnch_mcp.exec.policy import ExecDenied, load_exec_policy

router = APIRouter(prefix="/exec", tags=["exec"])

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
    candidates = [
        c for c in (xnch_settings.capability_token, xnch_settings.exec_agent_token) if c
    ]
    if not candidates:
        # Fail CLOSED: an unconfigured token on a 0.0.0.0-bound exec service
        # must be a loud misconfiguration, never silent open access.
        raise HTTPException(status_code=503, detail="capability-agent token not configured")
    if not token or not any(secrets.compare_digest(token, c) for c in candidates):
        raise HTTPException(status_code=401, detail="invalid internal token")


class RunRequest(BaseModel):
    command: str
    cwd: str | None = None


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST, "capability": "exec"}


@router.post("/run")
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