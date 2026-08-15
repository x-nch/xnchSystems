"""Mic capture, WAV building, and playback for the command center daemon."""

from __future__ import annotations

import io
import queue
import wave
from typing import Callable

import numpy as np

from .config import DaemonConfig
from .segmenter import VadSegmenter


def pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def capture_loop(
    segmenter: VadSegmenter,
    config: DaemonConfig,
    on_segment: Callable[[bytes], None],
) -> None:
    """Blocking mic stream → VAD → segmenter.feed() → on_segment()."""
    import sounddevice as sd
    import webrtcvad

    sample_rate = config.sample_rate
    frame_bytes = segmenter.chunk_bytes
    vad = webrtcvad.Vad(2)
    blocks: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status) -> None:
        blocks.put(indata.tobytes())

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=frame_bytes,
        device=config.input_device,
        callback=callback,
    ):
        while True:
            block = blocks.get()
            if not segmenter.armed or len(block) < frame_bytes:
                continue
            frame = block[:frame_bytes]
            is_speech = vad.is_speech(frame, sample_rate)
            segment = segmenter.feed(frame, is_speech)
            if segment is not None:
                on_segment(segment)


def play_wav(wav_bytes: bytes, *, device: int | str | None = None) -> None:
    import sounddevice as sd

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        sr = wf.getframerate()
        channels = wf.getnchannels()
    audio = np.frombuffer(pcm, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)
    sd.play(audio, sr, device=device)
    sd.wait()
