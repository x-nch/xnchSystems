"""WebRTC-VAD-style utterance segmentation for the capture loop."""

from __future__ import annotations

import collections


class VadSegmenter:
    """Buffers 30ms speech chunks and cuts utterances on trailing silence.

    feed() returns the completed segment (raw int16 PCM) when trailing
    silence reaches silence_ms or the max duration is hit; otherwise None.
    While disarmed, all input is ignored.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_ms: int = 30,
        silence_ms: int = 600,
        max_ms: int = 15000,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.chunk_bytes = sample_rate * chunk_ms // 1000 * 2
        self.silence_limit = silence_ms // chunk_ms
        self.max_chunks = max_ms // chunk_ms
        self._armed = False
        self._buffer = bytearray()
        self._in_utterance = False
        self._silence = 0
        self._chunks = 0

    @property
    def armed(self) -> bool:
        return self._armed

    def set_armed(self, armed: bool) -> None:
        self._armed = armed

    def feed(self, chunk: bytes, is_speech: bool) -> bytes | None:
        if not self._armed or len(chunk) != self.chunk_bytes:
            return None
        if is_speech and not self._in_utterance:
            self._in_utterance = True
            self._buffer = bytearray()
            self._silence = 0
            self._chunks = 0
        if not self._in_utterance:
            return None
        self._buffer.extend(chunk)
        self._chunks += 1
        self._silence = 0 if is_speech else self._silence + 1
        if self._silence >= self.silence_limit or self._chunks >= self.max_chunks:
            return self.flush()
        return None

    def flush(self) -> bytes | None:
        """Return the in-progress segment (min 600ms), or None."""
        if not self._in_utterance:
            return None
        segment = bytes(self._buffer)
        self._in_utterance = False
        self._buffer = bytearray()
        self._silence = 0
        self._chunks = 0
        if len(segment) < self.chunk_bytes * 20:
            return None
        return segment


def is_garbage(text: str) -> bool:
    """Reject too-short or >50% repeated-character transcripts."""
    chars = text.replace(" ", "")
    if len(chars) < 3:
        return True
    top = collections.Counter(chars).most_common(1)[0][1]
    return top / len(chars) > 0.5
