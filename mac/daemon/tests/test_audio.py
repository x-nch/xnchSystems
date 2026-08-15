import io
import wave

from daemon.audio import pcm_to_wav_bytes


def test_pcm_to_wav_bytes_wraps_header():
    pcm = b"\x00\x00" * 1600  # 0.1s @ 16kHz
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getnframes() == 1600
        assert wf.readframes(1600) == pcm
