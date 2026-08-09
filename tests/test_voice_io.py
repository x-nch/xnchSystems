"""Unit tests for cli/voice_io resampling helpers."""

from __future__ import annotations

import numpy as np

from cli.voice_io import _effective_playback_rate, _resample_int16


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
