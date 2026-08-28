"""Tests for local FS backend and MCP fs handlers."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from xnch_mcp.context import ActorContext
from xnch_mcp.fs.local import LocalFsBackend
from xnch_mcp.fs.policy import load_fs_policy
from xnch_mcp.fs.service import FsReadService
from xnch_mcp.handlers import fs as fs_handlers
from xnch_mcp.registry import list_tools_for_actor


@pytest.fixture
def fs_setup(tmp_path: Path) -> tuple[FsReadService, Path]:
    root = tmp_path / "home"
    root.mkdir()
    (root / "nexi").mkdir()
    (root / "nexi" / "main.py").write_text("print('nexi')\n")
    (root / ".xnch").mkdir()
    (root / ".xnch" / "xnch.env").write_text("SECRET=1")

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        f"""
hosts:
  node-a:
    roots:
      - {root}
  node-b:
    roots:
      - {root}
deny_globs:
  - "**/xnch.env"
  - "**/nexi.env"
"""
    )
    policy = load_fs_policy(policy_path)
    svc = FsReadService(policy, local_host="node-a", max_read_bytes=1024)
    return svc, root


def test_local_read(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, _ = fs_setup
    backend = LocalFsBackend(svc._policy, "node-a")
    result = backend.read("nexi/main.py")
    assert "print('nexi')" in result["content"]
    assert result["encoding"] == "utf-8"


def test_local_list(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, _ = fs_setup
    backend = LocalFsBackend(svc._policy, "node-a")
    result = backend.list_dir("nexi")
    names = {e["name"] for e in result["entries"]}
    assert "main.py" in names


@pytest.mark.asyncio
async def test_handler_read(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, _ = fs_setup
    app = MagicMock()
    app.fs_read_service = svc
    actor = ActorContext(actor_role="nexi", trace_id="t1")
    result = await fs_handlers._fs_read(app, actor, {"host": "node-a", "path": "nexi/main.py"})
    assert "nexi" in result["content"]


@pytest.mark.asyncio
async def test_handler_denied_env(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, _ = fs_setup
    app = MagicMock()
    app.fs_read_service = svc
    actor = ActorContext(actor_role="nexi", trace_id="t1")
    with pytest.raises(Exception):
        await fs_handlers._fs_read(app, actor, {"host": "node-a", "path": ".xnch/xnch.env"})


def test_fs_tools_hidden_from_opencode() -> None:
    names = {t.name for t in list_tools_for_actor("opencode")}
    assert "xnch_fs_read" not in names


def test_fs_tools_visible_for_nexi() -> None:
    names = {t.name for t in list_tools_for_actor("nexi")}
    assert "xnch_fs_read" in names
    assert "xnch_fs_list" in names


@pytest.mark.asyncio
async def test_remote_dispatch(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, _ = fs_setup
    remote = AsyncMock()
    remote.read = AsyncMock(return_value={"host": "node-b", "content": "remote"})
    svc._remote["node-b"] = remote

    result = await svc.read("node-b", "nexi/main.py")
    assert result["content"] == "remote"
    remote.read.assert_awaited_once()


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    nsmap = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }
    body = "".join(
        f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{nsmap["w"]}">{body}</w:document>'
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", document)
        zf.writestr("[Content_Types].xml", "")


def test_local_read_docx_extracts_text(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, root = fs_setup
    doc = root / "resume.docx"
    _write_docx(doc, ["Software Engineer", "Builds pipelines and APIs"])
    backend = LocalFsBackend(svc._policy, "node-a")
    result = backend.read("resume.docx")
    assert result["encoding"] == "extracted"
    assert "Software Engineer" in result["content"]
    assert "Builds pipelines" in result["content"]


def test_local_read_binary_falls_back_to_base64(fs_setup: tuple[FsReadService, Path]) -> None:
    svc, root = fs_setup
    blob = root / "blob.bin"
    blob.write_bytes(b"\x00\x01\x02\x80\xff")
    backend = LocalFsBackend(svc._policy, "node-a")
    result = backend.read("blob.bin")
    # Non-UTF8, non-office binary must keep the base64 behaviour.
    assert result["encoding"] == "base64"
