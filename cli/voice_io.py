"""Microphone capture and playback for gate7 CLI voice mode."""

from __future__ import annotations

import io
import os
import wave
from typing import Any

import numpy as np

_SAMPLE_RATE = int(os.environ.get("XNCH_VOICE_SAMPLE_RATE", "16000"))
_CHANNELS = 1


def list_devices() -> list[dict[str, Any]]:
    import sounddevice as sd

    devices = sd.query_devices()
    result: list[dict[str, Any]] = []
    for idx, dev in enumerate(devices):
        result.append(
            {
                "index": idx,
                "name": dev["name"],
                "max_input_channels": dev["max_input_channels"],
                "max_output_channels": dev["max_output_channels"],
                "default_samplerate": dev["default_samplerate"],
            }
        )
    return result


def _input_device() -> int | None:
    raw = os.environ.get("XNCH_VOICE_INPUT_DEVICE", "").strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw  # type: ignore[return-value]


def _output_device() -> int | None:
    raw = os.environ.get("XNCH_VOICE_OUTPUT_DEVICE", "").strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw  # type: ignore[return-value]


def record_seconds(duration_s: float) -> bytes:
    import sounddevice as sd

    frames = int(duration_s * _SAMPLE_RATE)
    audio = sd.rec(
        frames,
        samplerate=_SAMPLE_RATE,
        channels=_CHANNELS,
        dtype="int16",
        device=_input_device(),
    )
    sd.wait()
    return audio.tobytes()


def record_until_release(poll_interval_s: float = 0.1) -> bytes:
    """Record while Space is held (terminal must be focused)."""
    import sys
    import termios
    import tty

    import sounddevice as sd

    chunks: list[bytes] = []
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            chunk_frames = int(poll_interval_s * _SAMPLE_RATE)
            block = sd.rec(
                chunk_frames,
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype="int16",
                device=_input_device(),
            )
            sd.wait()
            chunks.append(block.tobytes())
            if sys.stdin in select_ready(fd, timeout=poll_interval_s):
                ch = sys.stdin.read(1)
                if ch == " ":
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return b"".join(chunks)


def select_ready(fd: int, timeout: float) -> bool:
    import select

    r, _, _ = select.select([fd], [], [], timeout)
    return bool(r)


def pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = _SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _resample_int16(mono: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Linear resample mono int16 PCM (Piper is 22050 Hz; ALSA hw often wants 44100)."""
    if src_sr == dst_sr or len(mono) == 0:
        return mono
    dst_len = max(1, int(round(len(mono) * dst_sr / src_sr)))
    x_src = np.arange(len(mono), dtype=np.float64)
    x_dst = np.linspace(0, len(mono) - 1, num=dst_len)
    return np.interp(x_dst, x_src, mono.astype(np.float64)).astype(np.int16)


def _effective_playback_rate(device: int | str | None, wav_sr: int) -> int:
    import sounddevice as sd

    if device is None:
        return wav_sr
    try:
        info = sd.query_devices(device, "output")
    except Exception:
        return wav_sr
    name = str(info.get("name", "")).lower()
    if "pulse" in name or name in {"default", "sysdefault"}:
        return wav_sr
    return int(info.get("default_samplerate", 44100))


def play_wav(wav_bytes: bytes) -> None:
    import sounddevice as sd

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        sr = wf.getframerate()
        channels = wf.getnchannels()
    audio = np.frombuffer(pcm, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)
    device = _output_device()
    target_sr = _effective_playback_rate(device, sr)
    if target_sr != sr:
        if audio.ndim > 1:
            audio = np.column_stack(
                [_resample_int16(audio[:, ch], sr, target_sr) for ch in range(audio.shape[1])]
            )
        else:
            audio = _resample_int16(audio, sr, target_sr)
        sr = target_sr
    sd.play(audio, sr, device=device)
    sd.wait()
