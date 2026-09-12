"""Remote client endpoint paths + capability-first settings fallback."""

from __future__ import annotations

import httpx

from xnch_mcp.exec.remote_client import ExecRemoteClient
from xnch_mcp.exec.service import ExecRunService
from xnch_mcp.fs.remote_client import FsRemoteClient
from xnch_mcp.fs.service import FsReadService


async def test_exec_remote_client_hits_exec_paths() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"exit_code": 0, "stdout": "ok"})

    client = ExecRemoteClient("http://node-b:8090", token="t", transport=httpx.MockTransport(handler))
    result = await client.run("echo hi")
    assert result["exit_code"] == 0
    assert seen == ["/exec/run"]

    await client.health()
    assert seen == ["/exec/run", "/exec/health"]


async def test_fs_remote_client_hits_fs_paths() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"exists": True})

    client = FsRemoteClient("http://node-b:8090", token="t", transport=httpx.MockTransport(handler))
    await client.exists("/tmp/x")
    await client.read("/tmp/x")
    await client.list_dir("/tmp")
    await client.stat("/tmp/x")
    await client.glob("*.txt")
    await client.health()
    assert seen == [
        "/fs/exists",
        "/fs/read",
        "/fs/list",
        "/fs/stat",
        "/fs/glob",
        "/fs/health",
    ]


def test_exec_service_prefers_capability_url() -> None:
    class S:
        exec_policy_path = "/nonexistent/exec-policy.yaml"
        exec_local_host = "node-a"
        capability_node_b_url = "http://192.168.50.2:8090"
        capability_token = "shared"

    svc = ExecRunService.from_settings(S())
    assert svc._remote["node-b"]._base_url == "http://192.168.50.2:8090"
    assert svc._remote["node-b"]._headers["X-Internal-Token"] == "shared"


def test_fs_service_prefers_capability_url() -> None:
    class S:
        fs_policy_path = "/nonexistent/fs-policy.yaml"
        fs_local_host = "node-a"
        capability_node_b_url = "http://192.168.50.2:8090"
        capability_token = "shared"

    svc = FsReadService.from_settings(S())
    assert svc._remote["node-b"]._base_url == "http://192.168.50.2:8090"
    assert svc._remote["node-b"]._headers["X-Internal-Token"] == "shared"