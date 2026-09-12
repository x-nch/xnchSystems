"""Read-only filesystem router (capability sidecar, node-b)."""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(prefix="/fs", tags=["fs"])

_LOCAL_HOST = os.environ.get("XNCH_FS_LOCAL_HOST", "node-b")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST, "capability": "fs"}