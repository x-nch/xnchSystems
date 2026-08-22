"""Processing pipeline: extract → chunk → embed → store."""

from .chunk import chunk_content, chunk_text

__all__ = [
    "extract_content",
    "extract_from_url",
    "chunk_text",
    "chunk_content",
    "get_embeddings",
    "get_embedding",
]


def get_embedding(text: str) -> list[float]:
    """Lazy re-export to avoid importing xnch.memory at module load."""
    from xnch.memory.embeddings import embed_text
    return embed_text(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Lazy re-export to avoid importing xnch.memory at module load."""
    from xnch.memory.embeddings import embed_texts
    return embed_texts(texts)


def extract_content(*args, **kwargs):  # type: ignore[no-untyped-def]
    from .extract import extract_content as _extract_content
    return _extract_content(*args, **kwargs)


def extract_from_url(*args, **kwargs):  # type: ignore[no-untyped-def]
    from .extract import extract_from_url as _extract_from_url
    return _extract_from_url(*args, **kwargs)
