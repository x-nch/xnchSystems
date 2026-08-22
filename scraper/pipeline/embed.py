"""Text embedding via xnch's shared ONNX MiniLM-L6-v2 embedder.

Lazy re-exports from ``xnch.memory.embeddings`` so the scraper pipeline
uses the same 384-dim vectors as episodic memory without pulling in
the full xnch.memory package at import time.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_embeddings() -> Any:
    """Load xnch.memory.embeddings bypassing xnch/memory/__init__.py."""
    if "xnch.memory.embeddings" in __import__("sys").modules:
        return __import__("sys").modules["xnch.memory.embeddings"]

    mod_dir = Path(__file__).resolve().parent.parent.parent / "xnch" / "memory"
    spec = importlib.util.spec_from_file_location(
        "xnch.memory.embeddings",
        mod_dir / "embeddings.py",
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    __import__("sys").modules["xnch.memory.embeddings"] = mod
    return mod


def get_embedding(text: str) -> list[float]:
    mod = _load_embeddings()
    return mod.embed_text(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    mod = _load_embeddings()
    return mod.embed_texts(texts)


__all__ = ["get_embedding", "get_embeddings"]
