"""Tests for VAD utterance segmentation and the garbage filter."""

from daemon.segmenter import VadSegmenter, is_garbage

CHUNK = 480  # 30ms @ 16kHz int16


def _c(value: int = 1) -> bytes:
    return bytes([value]) * CHUNK


def test_disarmed_ignores_all_frames():
    s = VadSegmenter()
    for _ in range(50):
        assert s.feed(_c(), True) is None
    assert s.flush() is None


def test_segment_ends_after_silence():
    s = VadSegmenter()
    s.set_armed(True)
    for _ in range(30):
        assert s.feed(_c(), True) is None
    for _ in range(19):
        assert s.feed(_c(), False) is None
    seg = s.feed(_c(), False)  # 20th silence chunk trips the limit
    assert seg is not None
    assert len(seg) == CHUNK * 50
    assert not s.armed or s.flush() is None  # utterance consumed


def test_max_duration_caps_segment():
    s = VadSegmenter()
    s.set_armed(True)
    seg = None
    for _ in range(500):
        seg = s.feed(_c(), True)
        if seg is not None:
            break
    assert seg is not None
    assert len(seg) <= CHUNK * 500


def test_flush_returns_partial_utterance():
    s = VadSegmenter()
    s.set_armed(True)
    for _ in range(25):
        assert s.feed(_c(), True) is None
    assert s.flush() is not None


def test_flush_drops_short_segment():
    s = VadSegmenter()
    s.set_armed(True)
    for _ in range(10):
        assert s.feed(_c(), True) is None
    assert s.flush() is None  # < 600ms minimum


def test_garbage_filter():
    assert is_garbage("aa aaa aaa")
    assert is_garbage("ab")
    assert not is_garbage("what is the capital of france")
    assert not is_garbage("okay let me show you the dashboard")
