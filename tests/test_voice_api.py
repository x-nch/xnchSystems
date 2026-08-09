"""API tests for /nexi/voice/* endpoints."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.fixtures.voice.make_tone import make_tone_wav
from xnch.main import app as xnch_app
from xnch.voice.pipeline import VoiceChatResult
from xnch.voice.stt import TranscriptResult


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.event_log = MagicMock()
    state.event_log.emit = MagicMock()
    state.kv_cache = MagicMock()
    state.kv_cache.redis_client = MagicMock()
    state.pg_episodic = MagicMock()
    state.pg_episodic.has_identical_recent = AsyncMock(return_value=False)
    state.pg_episodic.store_episode = AsyncMock()
    state.working_memory = MagicMock()
    state.working_memory.append_turn = AsyncMock()
    state.graph_store = MagicMock()
    state.relationship_store = MagicMock()
    state.sensory_buffer = MagicMock()
    state.sensory_buffer.write_perception = AsyncMock(return_value="perception:voice:1")
    proactivity = MagicMock()
    proactivity.get_pending = AsyncMock(return_value=[])
    state._nexi_proactivity = proactivity
    return state


@pytest.fixture
def app_state(mock_state):
    xnch_app.state = mock_state
    return mock_state


@pytest.mark.asyncio
@patch("xnch.voice.pipeline.transcribe_pcm", new_callable=AsyncMock)
async def test_voice_transcribe(mock_stt, app_state):
    mock_stt.return_value = TranscriptResult(
        text="hello nexi", language="en", duration_s=0.5
    )
    wav = make_tone_wav()
    transport = ASGITransport(app=xnch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/nexi/voice/transcribe",
            files={"audio": ("t.wav", wav, "audio/wav")},
            data={"format": "wav", "sample_rate": "16000"},
        )
    assert resp.status_code == 200
    assert resp.json()["transcript"] == "hello nexi"


@pytest.mark.asyncio
@patch("xnch.voice.pipeline.synthesize_speech", new_callable=AsyncMock)
async def test_voice_speak(mock_tts, app_state):
    mock_tts.return_value = b"RIFF...."
    transport = ASGITransport(app=xnch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/nexi/voice/speak", json={"text": "Hello"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    mock_tts.assert_awaited_once()


@pytest.mark.asyncio
@patch("xnch.voice.pipeline.run_nexi_chat", new_callable=AsyncMock)
@patch("xnch.voice.pipeline.transcribe_pcm", new_callable=AsyncMock)
@patch("xnch.voice.pipeline.synthesize_speech", new_callable=AsyncMock)
async def test_voice_chat_full_loop(
    mock_tts, mock_stt, mock_chat, app_state
):
    mock_stt.return_value = TranscriptResult(
        text="status check", language="en", duration_s=1.0
    )
    mock_chat.return_value = ("All systems nominal.", "nexi-ornith")
    mock_tts.return_value = b"RIFFwav"

    wav = make_tone_wav()
    transport = ASGITransport(app=xnch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/nexi/voice/chat",
            files={"audio": ("t.wav", wav, "audio/wav")},
            data={
                "session_id": "voice-sess-1",
                "actor_role": "operator",
                "return_audio": "true",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "status check"
    assert body["response"] == "All systems nominal."
    assert body["audio_base64"] == base64.b64encode(b"RIFFwav").decode("ascii")
    app_state.sensory_buffer.write_perception.assert_awaited_once()
