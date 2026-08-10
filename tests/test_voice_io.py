"""Unit tests for cli/voice_io resampling helpers."""

from __future__ import annotations

import numpy as np

from cli.voice_io import (
    _effective_playback_rate,
    _resample_int16,
    resolve_output_device,
)


def test_resample_int16_changes_length() -> None:
    src = np.arange(22050, dtype=np.int16)
    out = _resample_int16(src, 22050, 44100)
    assert len(out) == 44100
    assert out.dtype == np.int16


def test_resample_int16_noop_same_rate() -> None:
    src = np.array([1, 2, 3], dtype=np.int16)
    assert np.array_equal(_resample_int16(src, 16000, 16000), src)


def test_effective_playback_rate_pulse_passthrough(monkeypatch) -> None:
    def fake_query(device, kind=None):
        return {"name": "pulse", "default_samplerate": 44100.0}

    monkeypatch.setattr("sounddevice.query_devices", fake_query)
    assert _effective_playback_rate(14, 22050) == 22050


def test_effective_playback_rate_hw_resamples(monkeypatch) -> None:
    def fake_query(device, kind=None):
        return {"name": "HDA Intel PCH: ALC255 Analog (hw:0,0)", "default_samplerate": 44100.0}

    monkeypatch.setattr("sounddevice.query_devices", fake_query)
    assert _effective_playback_rate(0, 22050) == 44100


def test_resolve_output_device_prefers_builtin_over_bt_default(monkeypatch) -> None:
    devices = [
        {"name": "HDMI", "max_output_channels": 2, "default_samplerate": 48000.0},
        {"name": "BT-5.0", "max_output_channels": 2, "default_samplerate": 44100.0},
        {"name": "MacBook Air Microphone", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "MacBook Air Speakers", "max_output_channels": 2, "default_samplerate": 48000.0},
    ]

    class FakeDefault:
        device = (2, 1)

    monkeypatch.setattr("sounddevice.query_devices", lambda: devices)
    monkeypatch.setattr("sounddevice.default", FakeDefault)
    monkeypatch.delenv("XNCH_VOICE_OUTPUT_DEVICE", raising=False)
    assert resolve_output_device() == 3


def test_resolve_output_device_honors_env(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_VOICE_OUTPUT_DEVICE", "0")
    assert resolve_output_device() == 0
