"""Dispatch filesystem reads to local backend or remote fs-read-agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xnch_mcp.fs.local import LocalFsBackend
from xnch_mcp.fs.policy import FsAccessDenied, FsPolicy, load_fs_policy
from xnch_mcp.fs.remote_client import FsRemoteClient


class FsReadService:
    def __init__(
        self,
        policy: FsPolicy,
        *,
        local_host: str = "node-a",
        remote_hosts: dict[str, FsRemoteClient] | None = None,
        max_read_bytes: int = 2_097_152,
        max_list_entries: int = 1000,
        max_glob_results: int = 200,
    ) -> None:
        self._policy = policy
        self._local_host = local_host
        self._remote = remote_hosts or {}
        self._max_read_bytes = max_read_bytes
        self._max_list_entries = max_list_entries
        self._max_glob_results = max_glob_results
        self._local = LocalFsBackend(policy, local_host)

    @classmethod
    def from_settings(cls, settings: Any) -> "FsReadService":
        policy_path = Path(settings.fs_policy_path)
        if not policy_path.is_file():
            repo_default = Path(__file__).resolve().parents[2] / "infra/no-k3s/shared/fs-policy.yaml"
            policy_path = repo_default if repo_default.is_file() else policy_path
        policy = load_fs_policy(policy_path)

        remote: dict[str, FsRemoteClient] = {}
        node_b_url = getattr(settings, "fs_agent_node_b_url", "") or ""
        token = getattr(settings, "fs_agent_token", "") or ""
        if node_b_url:
            remote["node-b"] = FsRemoteClient(node_b_url, token=token)

        return cls(
            policy,
            local_host=getattr(settings, "fs_local_host", "node-a"),
            remote_hosts=remote,
            max_read_bytes=getattr(settings, "fs_max_read_bytes", 2_097_152),
            max_list_entries=getattr(settings, "fs_max_list_entries", 1000),
            max_glob_results=getattr(settings, "fs_max_glob_results", 200),
        )

    def _backend(self, host: str) -> LocalFsBackend | FsRemoteClient:
        if host == self._local_host:
            return self._local
        client = self._remote.get(host)
        if client is None:
            raise FsAccessDenied(f"no filesystem backend configured for host {host}")
        return client

    async def list_dir(
        self,
        host: str,
        path: str,
        *,
        recursive: bool = False,
    ) -> dict[str, Any]:
        backend = self._backend(host)
        if isinstance(backend, LocalFsBackend):
            return backend.list_dir(path, recursive=recursive, max_entries=self._max_list_entries)
        return await backend.list_dir(path, recursive=recursive, max_entries=self._max_list_entries)

    async def read(
        self,
        host: str,
        path: str,
        *,
        offset: int = 0,
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        cap = min(max_bytes or self._max_read_bytes, self._max_read_bytes)
        backend = self._backend(host)
        if isinstance(backend, LocalFsBackend):
            return backend.read(path, offset=offset, max_bytes=cap)
        return await backend.read(path, offset=offset, max_bytes=cap)

    async def stat(self, host: str, path: str) -> dict[str, Any]:
        backend = self._backend(host)
        if isinstance(backend, LocalFsBackend):
            return backend.stat(path)
        return await backend.stat(path)

    async def exists(self, host: str, path: str) -> dict[str, Any]:
        backend = self._backend(host)
        if isinstance(backend, LocalFsBackend):
            return backend.exists(path)
        return await backend.exists(path)

    async def glob(self, host: str, pattern: str) -> dict[str, Any]:
        backend = self._backend(host)
        if isinstance(backend, LocalFsBackend):
            return backend.glob(pattern, max_results=self._max_glob_results)
        return await backend.glob(pattern, max_results=self._max_glob_results)
