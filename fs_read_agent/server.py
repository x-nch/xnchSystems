"""Read-only filesystem HTTP agent (node-b sidecar for xnch MCP)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from xnch.config import settings as xnch_settings
from xnch_mcp.fs.local import LocalFsBackend
from xnch_mcp.fs.policy import FsAccessDenied, load_fs_policy

app = FastAPI(title="fs-read-agent", version="0.1.0")

_LOCAL_HOST = os.environ.get("XNCH_FS_LOCAL_HOST", "node-b")


def _policy_path() -> Path:
    path = xnch_settings.fs_policy_path
    if path.is_file():
        return path
    repo_default = Path(__file__).resolve().parents[1] / "infra/no-k3s/shared/fs-policy.yaml"
    return repo_default if repo_default.is_file() else path


_policy = load_fs_policy(_policy_path())
_backend = LocalFsBackend(_policy, _LOCAL_HOST)


def _verify_token(
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    expected = xnch_settings.fs_agent_token
    if not expected:
        # Fail CLOSED: unconfigured token on a 0.0.0.0-bound service is a loud
        # misconfiguration, never silent open access.
        raise HTTPException(status_code=503, detail="fs-read-agent token not configured")
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid internal token")


def _deny(exc: FsAccessDenied) -> HTTPException:
    return HTTPException(status_code=403, detail=str(exc))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST}


@app.get("/list")
async def list_dir(
    path: str = Query("."),
    recursive: bool = Query(False),
    max_entries: int = Query(1000, ge=1, le=5000),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.list_dir(path, recursive=recursive, max_entries=max_entries)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/read")
async def read_file(
    path: str = Query(...),
    offset: int = Query(0, ge=0),
    max_bytes: int = Query(2_097_152, ge=1, le=10_485_760),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.read(path, offset=offset, max_bytes=max_bytes)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IsADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/stat")
async def stat_path(
    path: str = Query(...),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.stat(path)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc


@app.get("/exists")
async def exists_path(
    path: str = Query(...),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.exists(path)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc


@app.get("/glob")
async def glob_paths(
    pattern: str = Query(...),
    max_results: int = Query(200, ge=1, le=1000),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.glob(pattern, max_results=max_results)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def main() -> None:
    host = os.environ.get("XNCH_FS_AGENT_BIND", "127.0.0.1")
    port = int(os.environ.get("XNCH_FS_AGENT_PORT", "8003"))
    uvicorn.run("fs_read_agent.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
