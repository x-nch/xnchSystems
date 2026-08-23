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
    assert R.build_command(cfg, "do thing") == ["opencode", "run", "-p", "do thing"]


def test_handle_once_done_path(fake_xnch, tmp_path):
    url, seen = fake_xnch
    cfg = R.RunnerConfig(
        gateway_url=url, gateway_secret="s", runner_id="mac-runner",
        agent_command="true", agent_args="", timeout_s=60, poll_s=1,
    )
    result = R.handle_once(cfg)
    assert result == "done"
    assert seen["outcomes"] and seen["outcomes"][0]["outcome_status"] == "DONE"
    assert seen["outcomes"][0]["exit_code"] == 0
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
