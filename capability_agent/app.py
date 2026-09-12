"""Capability sidecar — one process for governed exec + read-only fs (node-b)."""

from __future__ import annotations

from fastapi import FastAPI

from capability_agent.exec_router import router as exec_router
from capability_agent.fs_router import router as fs_router

app = FastAPI(title="capability-agent", version="1.0.0")
app.include_router(exec_router)
app.include_router(fs_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "capabilities": "exec,fs"}