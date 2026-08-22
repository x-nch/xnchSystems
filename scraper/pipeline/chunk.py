"""Text chunking for RAG embedding."""

import logging
import re
from uuid import uuid4

from ..models import ContentChunk, ExtractedContent

logger = logging.getLogger(__name__)

# Approximate chars-per-token ratio for chunk sizing.
_CHARS_PER_TOKEN = 4


def chunk_text(
    text: str,
    source_url: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[ContentChunk]:
    """Split text into overlapping chunks for embedding.

    chunk_size and overlap are in *tokens* (~4 chars each).
    Splits prefer paragraph boundaries, then sentence boundaries,
    then hard character splits.
    """
    char_limit = chunk_size * _CHARS_PER_TOKEN
    overlap_chars = overlap * _CHARS_PER_TOKEN

    if not text.strip():
        return []

    raw_chunks = _split_text(text, char_limit, overlap_chars)
    total = len(raw_chunks)

    chunks: list[ContentChunk] = []
    for i, chunk_text_piece in enumerate(raw_chunks):
        chunks.append(
            ContentChunk(
                chunk_id=str(uuid4()),
                source_url=source_url,
                text=chunk_text_piece,
                index=i,
                total_chunks=total,
                metadata={},
            )
        )
    return chunks


def chunk_content(
    content: ExtractedContent,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[ContentChunk]:
    """Convenience wrapper: chunk an ExtractedContent's markdown."""
    return chunk_text(content.markdown, content.url, chunk_size, overlap)


# ---------------------------------------------------------------------------
# Internal splitting helpers
# ---------------------------------------------------------------------------


def _split_text(text: str, char_limit: int, overlap_chars: int) -> list[str]:
    """Recursively split text respecting paragraph → sentence → hard boundaries."""
    paragraphs = text.split("\n\n")
    result: list[str] = []
    buffer = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = f"{buffer}\n\n{para}" if buffer else para

        if len(candidate) <= char_limit:
            buffer = candidate
        else:
            if buffer:
                result.append(buffer)
            # If single paragraph exceeds limit, split further
            if len(para) > char_limit:
                sub_chunks = _split_by_sentences(para, char_limit, overlap_chars)
                result.extend(sub_chunks)
                buffer = ""
            else:
                buffer = para

    if buffer:
        result.append(buffer)

    if not result:
        return []

    return _apply_overlap(result, overlap_chars)


def _split_by_sentences(text: str, char_limit: int, overlap_chars: int) -> list[str]:
    """Split a paragraph by sentence boundaries, then hard split if needed."""
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result: list[str] = []
    buffer = ""

    for sent in sentences:
        candidate = f"{buffer} {sent}" if buffer else sent

        if len(candidate) <= char_limit:
            buffer = candidate
        else:
            if buffer:
                result.append(buffer)
            if len(sent) > char_limit:
                # Hard split as last resort
                hard_chunks = _hard_split(sent, char_limit)
                result.extend(hard_chunks)
                buffer = ""
            else:
                buffer = sent

    if buffer:
        result.append(buffer)

    return result


def _hard_split(text: str, char_limit: int) -> list[str]:
    """Last-resort: split text at exact character boundaries."""
    return [text[i : i + char_limit] for i in range(0, len(text), char_limit)]


def _apply_overlap(chunks: list[str], overlap_chars: int) -> list[str]:
    """Prepend tail of previous chunk to the next for context continuity."""
    if overlap_chars <= 0 or len(chunks) < 2:
        return chunks

    overlapped: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap_chars:]
        # Find a clean break point in the tail (space boundary)
        space_idx = prev_tail.find(" ")
        if space_idx > 0:
            prev_tail = prev_tail[space_idx + 1 :]
        overlapped.append(f"{prev_tail} {chunks[i]}")
    return overlapped
