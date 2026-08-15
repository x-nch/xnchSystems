import base64

import httpx

from daemon.config import DaemonConfig
from daemon.gateway import GatewayClient


def _cfg() -> DaemonConfig:
    return DaemonConfig(
        base_url="http://xnch:8001",
        auth_secret="s3cret",
        auth_token="",
        actor="operator",
        nexi_url="http://nexi:8001",
        media_url="http://media:8090",
        sample_rate=16000,
        input_device=None,
        output_device=None,
        ws_host="127.0.0.1",
        ws_port=9001,
        http_port=9002,
    )


def test_voice_chat_builds_multipart_and_parses():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/nexi/voice/chat"
        assert request.method == "POST"
        body = request.content.decode("utf-8", errors="ignore")
        assert "name=\"audio\"" in body
        assert "name=\"session_id\"" in body and "cc-s1" in body
        assert "name=\"actor_role\"" in body and "operator" in body
        return httpx.Response(200, json={
            "transcript": "hello",
            "response": "hi",
            "session_id": "cc-s1",
            "audio_base64": base64.b64encode(b"RIFF").decode(),
        })

    gw = GatewayClient(_cfg(), transport=httpx.MockTransport(handler))
    data = gw.voice_chat(b"\x00\x00", session_id="cc-s1")
    assert data["transcript"] == "hello"
    assert data["session_id"] == "cc-s1"


def test_health_endpoints():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    gw = GatewayClient(_cfg(), transport=httpx.MockTransport(handler))
    assert gw.health()["status"] == "ok"
    assert gw.nexi_health()["status"] == "ok"
    assert gw.media_health()["status"] == "ok"
