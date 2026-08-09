"""Generate a minimal 16-bit mono WAV fixture for voice tests."""

from __future__ import annotations

import io
import math
import struct
import wave


def make_tone_wav(
    *,
    duration_s: float = 0.5,
    sample_rate: int = 16000,
    frequency_hz: float = 440.0,
    amplitude: float = 0.2,
) -> bytes:
    n_frames = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            sample = int(
                amplitude * 32767.0 * math.sin(2.0 * math.pi * frequency_hz * i / sample_rate)
            )
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(bytes(frames))
    return buf.getvalue()
