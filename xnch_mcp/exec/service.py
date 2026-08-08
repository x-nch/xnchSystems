"""Dispatch command execution to local backend or remote exec-agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xnch_mcp.exec.local import LocalExecBackend
from xnch_mcp.exec.policy import ExecDenied, ExecPolicy, load_exec_policy
from xnch_mcp.exec.remote_client import ExecRemoteClient


class ExecRunService:
    def __init__(
        self,
        policy: ExecPolicy,
        *,
        local_host: str = "node-a",
        remote_hosts: dict[str, ExecRemoteClient] | None = None,
    ) -> None:
        self._policy = policy
        self._local_host = local_host
        self._remote = remote_hosts or {}
        self._local = LocalExecBackend(policy, local_host)

    @classmethod
    def from_settings(cls, settings: Any) -> "ExecRunService":
        policy_path = Path(settings.exec_policy_path)
        if not policy_path.is_file():
            repo_default = (
                Path(__file__).resolve().parents[2] / "infra/no-k3s/shared/exec-policy.yaml"
            )
            policy_path = repo_default if repo_default.is_file() else policy_path
        policy = load_exec_policy(policy_path)

        remote: dict[str, ExecRemoteClient] = {}
        node_b_url = getattr(settings, "exec_agent_node_b_url", "") or ""
        token = getattr(settings, "exec_agent_token", "") or ""
        if node_b_url:
            remote["node-b"] = ExecRemoteClient(node_b_url, token=token)

        return cls(
            policy,
            local_host=getattr(settings, "exec_local_host", "node-a"),
            remote_hosts=remote,
        )

    async def run(self, host: str, command: str, *, cwd: str | None = None) -> dict[str, Any]:
        if host == self._local_host:
            return await self._local.run(command, cwd=cwd)
        client = self._remote.get(host)
        if client is None:
            raise ExecDenied(f"no exec backend configured for host {host}")
        return await client.run(command, cwd=cwd)
