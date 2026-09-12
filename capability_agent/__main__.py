"""Run the capability sidecar (defaults: 127.0.0.1:8090)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("XNCH_CAPABILITY_BIND", "127.0.0.1")
    port = int(os.environ.get("XNCH_CAPABILITY_PORT", "8090"))
    uvicorn.run("capability_agent.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()