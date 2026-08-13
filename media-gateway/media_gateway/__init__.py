"""media-gateway — REST orchestrator for the Node B vision stack.

Standalone FastAPI service (its own venv on Node B, systemd
media-gateway.service) that exposes a token-protected surface for uploading
local media, dispatching understand/edit/generate jobs, and pulling results.
"""

from .config import Settings
from .main import create_app, app

__all__ = ["Settings", "create_app", "app"]
