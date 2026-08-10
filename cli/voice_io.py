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


def resolve_input_device() -> int | str | None:
    """Pick mic: env override, else default input, else first input-capable device."""
    import sounddevice as sd

    explicit = _input_device()
    if explicit is not None:
        return explicit

    default_idx = sd.default.device[0]
    if default_idx is not None:
        info = sd.query_devices(default_idx)
        if info.get("max_input_channels", 0) > 0:
            return default_idx

    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0:
            return idx
    return None


def pcm_stats(pcm: bytes) -> dict[str, float]:
    """Peak and RMS for mono int16 PCM (diagnose silent / blocked mic)."""
    if len(pcm) < 2:
        return {"peak": 0.0, "rms": 0.0, "duration_s": 0.0}
    mono = np.frombuffer(pcm, dtype=np.int16)
    peak = float(np.max(np.abs(mono)))
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
    duration_s = len(mono) / float(_SAMPLE_RATE)
    return {"peak": peak, "rms": rms, "duration_s": duration_s}


def is_silent_pcm(pcm: bytes, *, peak_threshold: int = 150) -> bool:
    return pcm_stats(pcm)["peak"] < peak_threshold


def describe_input_device() -> str:
    import sounddevice as sd

    device = resolve_input_device()
    if device is None:
        return "no input device"
    info = sd.query_devices(device, "input")
    return f"[{device}] {info.get('name', device)}"


def _output_device() -> int | str | None:
    raw = os.environ.get("XNCH_VOICE_OUTPUT_DEVICE", "").strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw


def _is_bluetooth_output(name: str) -> bool:
    lowered = name.lower()
    return "bt-" in lowered or "bluetooth" in lowered or "airpods" in lowered


def _is_builtin_speaker(name: str) -> bool:
    lowered = name.lower()
    if "microphone" in lowered or " mic" in lowered:
        return False
    return "speaker" in lowered or "built-in" in lowered or "macbook" in lowered


def resolve_output_device() -> int | str | None:
    """Pick speaker: env override, else avoid stale BT default on macOS."""
    import sounddevice as sd

    explicit = _output_device()
    if explicit is not None:
        return explicit

    devices = sd.query_devices()
    default_idx = sd.default.device[1]
    if default_idx is not None:
        default_info = devices[default_idx]
        default_name = str(default_info.get("name", ""))
        if (
            default_info.get("max_output_channels", 0) > 0
            and _is_bluetooth_output(default_name)
        ):
            for idx, dev in enumerate(devices):
                name = str(dev.get("name", ""))
                if dev.get("max_output_channels", 0) > 0 and _is_builtin_speaker(name):
                    return idx

        if default_info.get("max_output_channels", 0) > 0:
            return default_idx

    for idx, dev in enumerate(devices):
        if dev.get("max_output_channels", 0) > 0:
            return idx
    return None


def describe_output_device() -> str:
    import sounddevice as sd

    device = resolve_output_device()
    if device is None:
        return "no output device"
    info = sd.query_devices(device, "output")
    return f"[{device}] {info.get('name', device)}"


def record_seconds(duration_s: float) -> bytes:
    import sounddevice as sd

    device = resolve_input_device()
    if device is None:
        raise RuntimeError("No microphone input device found")

    native_sr = _SAMPLE_RATE
    if device is not None:
        try:
            native_sr = int(sd.query_devices(device, "input").get("default_samplerate", _SAMPLE_RATE))
        except Exception:
            native_sr = _SAMPLE_RATE

    frames = int(duration_s * native_sr)
    audio = sd.rec(
        frames,
        samplerate=native_sr,
        channels=_CHANNELS,
        dtype="int16",
        device=device,
    )
    sd.wait()
    pcm = audio.tobytes()
    if native_sr != _SAMPLE_RATE:
        mono = np.frombuffer(pcm, dtype=np.int16)
        pcm = _resample_int16(mono, native_sr, _SAMPLE_RATE).tobytes()
    return pcm


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
                device=resolve_input_device(),
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
    device = resolve_output_device()
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
