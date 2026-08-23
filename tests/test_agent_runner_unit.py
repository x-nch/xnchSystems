"""Offline unit tests for the xnch agent-runner (stdlib-only module).

Uses a local http.server fixture as a stand-in xnch: serves one claimable run,
records the outcome POST, then 204s. Verifies command assembly, token header,
claim->execute->outcome flow for both DONE and FAILED paths.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent-runner"))

from xnch_agent_runner import runner as R  # noqa: E402


@pytest.fixture()
def fake_xnch(tmp_path):
    seen: dict = {"claims": [], "outcomes": []}
    state = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def _send(self, code, body=None):
            raw = json.dumps(body).encode() if body is not None else b""
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            assert "X-Gateway-Token" in self.headers, "runner must authenticate"
            if self.path == "/agents/dispatch/next":
                state["n"] += 1
                seen["claims"].append(payload)
                if state["n"] == 1:
                    self._send(200, {
                        "id": "run-1", "status": "RUNNING",
                        "prompt": "make hello.txt",
                        "workspace": str(tmp_path / "ws"),
                    })
                else:
                    self._send(204)
                return
            if self.path.startswith("/agents/runs/") and self.path.endswith("/outcome"):
                seen["outcomes"].append(payload)
                self._send(200, {"id": "run-1"})
                return
            self._send(404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", seen
    srv.shutdown()


def test_build_command_appends_prompt_flag():
    cfg = R.RunnerConfig(
        gateway_url="http://x", gateway_secret="s", runner_id="r",
        agent_command="opencode", agent_args="run", timeout_s=60, poll_s=1,
    )
    assert R.build_command(cfg, "do thing") == ["opencode", "run", "--", "do thing"]


def test_handle_once_done_path(fake_xnch, tmp_path):
    url, seen = fake_xnch
    cfg = R.RunnerConfig(
        gateway_url=url, gateway_secret="s", runner_id="mac-runner",
        agent_command="true", agent_args="", timeout_s=60, poll_s=1,
    )
    class FakeProc:
        returncode = 0
        stdout = "final agent answer text"
        stderr = ""

    result = R.handle_once(cfg, spawn=lambda *a, **k: FakeProc())
    assert result == "done"
    out = seen["outcomes"][0]
    assert out["outcome_status"] == "DONE" and out["exit_code"] == 0
    assert out["result_text"] == "final agent answer text"  # shipped to xnch
    assert seen["claims"][0]["runner_id"] == "mac-runner"


def test_handle_once_empty_204(fake_xnch):
    url, seen = fake_xnch
    cfg = R.RunnerConfig(
        gateway_url=url, gateway_secret="s", runner_id="r",
        agent_command="true", agent_args="", timeout_s=5, poll_s=1,
    )
    # First claim consumed by prior test? No — fresh server per test; burn the one run.
    R.handle_once(cfg)
    seen["outcomes"].clear()
    assert R.handle_once(cfg) == "empty"


def test_spawn_env_allowlist_drops_secrets():
    """Only a fixed allowlist may reach the spawned coding-agent process."""
    dirty = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/Users/xnch",
        "USER": "xnch",
        "XNCH_GATEWAY_SECRET": "super-secret-value",
        "AWS_SECRET_ACCESS_KEY": "leak-me",
        "HTTP_PROXY": "http://evil:3128",
    }
    env = R._spawn_env(dirty)
    assert env["PATH"] == "/usr/bin:/bin" and env["HOME"] == "/Users/xnch"
    assert "XNCH_GATEWAY_SECRET" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "HTTP_PROXY" not in env


def test_spawn_env_injects_required_defaults():
    env = R._spawn_env({})
    assert env.get("HOME"), "child needs HOME for opencode auth/config paths"
    assert env.get("PATH"), "child needs PATH"


def test_handle_once_writes_workspace_provider_policy(fake_xnch, tmp_path):
    """Each dispatch workspace gets a project opencode.json denying all LLM
    providers except the local LiteLLM one (scoped provider firewall)."""
    url, seen = fake_xnch
    cfg = R.RunnerConfig(
        gateway_url=url, gateway_secret="s", runner_id="r",
        agent_command="true", agent_args="run --agent xnch-dispatch",
        timeout_s=5, poll_s=1,
    )
    R.handle_once(cfg)
    ws_cfg = json.loads((tmp_path / "ws" / "opencode.json").read_text())
    policies = ws_cfg["experimental"]["policies"]
    deny_any = [p for p in policies if p["effect"] == "deny" and p["resource"] == "*"]
    allow_local = [p for p in policies if p["effect"] == "allow" and p["resource"] == R.ALLOWED_PROVIDER_ID]
    assert deny_any and allow_local


def test_handle_once_scopes_sandbox_plugin_to_workspace(fake_xnch, tmp_path, monkeypatch):
    """U3: the Seatbelt sandbox plugin is loaded ONLY inside dispatch
    workspaces (project-level plugin entry + strict inline config); spawned
    process receives OPENCODE_SANDBOX_CONFIG; interactive sessions untouched."""
    url, seen = fake_xnch
    cfg = R.RunnerConfig(
        gateway_url=url, gateway_secret="s", runner_id="r",
        agent_command="/usr/bin/env", agent_args="run --agent xnch-dispatch",
        timeout_s=5, poll_s=1,
    )
    seen_env: dict = {}

    def spy(cmd, **kwargs):
        seen_env.update(kwargs.get("env") or {})
        # openocode isn't under test here; emulate success with no output path
        class P:
            returncode = 0
            stdout = ""
            stderr = ""
        return P()

    R.handle_once(cfg, spawn=spy)
    assert "OPENCODE_SANDBOX_CONFIG" in seen_env, "runner must pass sandbox config"
    import json as _json
    sb = _json.loads(seen_env["OPENCODE_SANDBOX_CONFIG"])
    assert "~/.ssh" in sb["filesystem"]["denyRead"]
    ws_cfg = _json.loads((tmp_path / "ws" / "opencode.json").read_text())
    assert "opencode-sandbox" in ws_cfg.get("plugin", [])


def test_config_rejects_unscoped_agent_command():
    """Fail-fast at config time if the spawned command would not pin the
    restricted agent (deny-by-default scope guard)."""
    import pytest
    with pytest.raises(SystemExit, match="agent"):
        R.RunnerConfig.from_env({
            "XNCH_GATEWAY_SECRET": "s",
            "XNCH_AGENT_COMMAND": "opencode",
            "XNCH_AGENT_ARGS": "run",  # no --agent -> unscoped
        })
    # Explicit override escape hatch is honored.
    cfg = R.RunnerConfig.from_env({
        "XNCH_GATEWAY_SECRET": "s",
        "XNCH_AGENT_COMMAND": "opencode",
        "XNCH_AGENT_ARGS": "run",
        "XNCH_ALLOW_UNSCOPED_AGENT": "1",
    })
    assert cfg.agent_args == "run"


def test_handle_once_failure_reports_error(fake_xnch):
    url, seen = fake_xnch
    cfg = R.RunnerConfig(
        gateway_url=url, gateway_secret="s", runner_id="r",
        agent_command="false", agent_args="", timeout_s=5, poll_s=1,
    )
    # Server hands out run-1 on first claim of THIS fixture instance.
    result = R.handle_once(cfg)
    assert result == "failed"
    last = seen["outcomes"][-1]
    assert last["outcome_status"] == "FAILED"
    assert "error" in last or last["exit_code"] != 0
