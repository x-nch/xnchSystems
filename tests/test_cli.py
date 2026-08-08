"""Tests for the xnch CLI client."""

import json
from unittest.mock import MagicMock, patch

import jwt
import pytest

from cli.client import XnchCliClient
from cli.config import CliConfig


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XNCH_BASE_URL", "http://test:8001")
    monkeypatch.setenv("XNCH_AUTH_SECRET", "test-secret-32bytes-long!!!!!!")
    monkeypatch.setenv("XNCH_ACTOR", "operator")
    return CliConfig.from_env()


def test_auth_header_uses_actor_prefix_when_no_secret(monkeypatch):
    monkeypatch.delenv("XNCH_AUTH_SECRET", raising=False)
    monkeypatch.delenv("XNCH_AUTH_TOKEN", raising=False)
    config = CliConfig(
        base_url="http://test:8001",
        auth_secret="",
        auth_token="",
        actor="operator",
        nexi_url="http://test:8000",
    )
    client = XnchCliClient(config)
    assert client.auth_header() == "actor:operator"
    client.close()


def test_auth_header_mints_jwt(config):
    client = XnchCliClient(config)
    header = client.auth_header()
    assert header.startswith("Bearer ")
    token = header.removeprefix("Bearer ")
    payload = jwt.decode(token, config.auth_secret, algorithms=["HS256"])
    assert payload["sub"] == "operator"
    client.close()


def test_session_init_posts_payload(config):
    client = XnchCliClient(config)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"status": "EXECUTING"}

    with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
        result = client.session_init("deploy myapp")

    assert result["status"] == "EXECUTING"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    body = call_kwargs.kwargs["json"]
    assert body["raw_input"] == "deploy myapp"
    assert body["source_system"] == "xnch-cli"
    assert body["auth_token"].startswith("Bearer ")
    client.close()


def test_session_id_persistence(config, tmp_path, monkeypatch):
    state_file = tmp_path / "cli_state.json"
    monkeypatch.setattr("cli.client._STATE_PATH", state_file)

    client = XnchCliClient(config)
    sid = client._load_session_id()
    assert sid.startswith("cli-")

    client._save_session_id("persisted-session")
    data = json.loads(state_file.read_text())
    assert data["session_id"] == "persisted-session"

    client2 = XnchCliClient(config)
    assert client2._load_session_id() == "persisted-session"
    client.close()
    client2.close()


def test_new_session_generates_and_persists(config, tmp_path, monkeypatch):
    state_file = tmp_path / "cli_state.json"
    monkeypatch.setattr("cli.client._STATE_PATH", state_file)

    client = XnchCliClient(config)
    sid = client.new_session()
    assert sid.startswith("cli-")
    assert json.loads(state_file.read_text())["session_id"] == sid
    client.close()


def test_clear_session_resets_to_fresh(config, tmp_path, monkeypatch):
    state_file = tmp_path / "cli_state.json"
    monkeypatch.setattr("cli.client._STATE_PATH", state_file)

    client = XnchCliClient(config)
    first = client.new_session()
    cleared = client.clear_session()
    assert cleared != first
    assert cleared.startswith("cli-")
    assert json.loads(state_file.read_text())["session_id"] == cleared
    client.close()


def test_mcp_call_posts_with_actor_header(config):
    client = XnchCliClient(config)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"name": "xnch_health", "result": {"status": "ok"}}

    with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
        result = client.mcp_call("xnch_health", actor_role="nexi")

    assert result["result"]["status"] == "ok"
    mock_post.assert_called_once()
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["X-Actor-Role"] == "nexi"
    client.close()


def test_parse_mcp_args():
    from cli.main import _parse_mcp_args

    assert _parse_mcp_args(["query=MCP bridge", "limit=3"]) == {
        "query": "MCP bridge",
        "limit": 3,
    }
    assert _parse_mcp_args(["enabled=true"]) == {"enabled": True}
