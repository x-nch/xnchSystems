"""Local read-only filesystem operations."""

from __future__ import annotations

import base64
import mimetypes
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from xnch_mcp.fs.policy import FsAccessDenied, FsPolicy


_TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json", ".jsonc", ".toml", ".ini",
    ".sh", ".service", ".timer", ".env.example", ".sql", ".html", ".css", ".js",
    ".ts", ".tsx", ".jsx", ".xml", ".csv", ".log", ".cfg", ".conf",
}


def _stat_entry(path: Path) -> dict[str, object]:
    st = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "type": "directory" if path.is_dir() else "file",
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "is_symlink": path.is_symlink(),
    }


_OFFICE_SUFFIXES = {".doc", ".docx", ".odt", ".rtf", ".pdf"}
_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _extract_docx(path: Path) -> str:
    """Extract plain text from a .docx (a zip of WordprocessingML XML)."""
    parts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml") or "word/" not in name:
                continue
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            for para in root.iter(f"{_DOCX_NS}p"):
                text = "".join(
                    t.text or "" for t in para.iter(f"{_DOCX_NS}t")
                )
                if text.strip():
                    parts.append(text)
    return "\n".join(parts).strip()


def _extract_doc(path: Path) -> str | None:
    """Extract text from legacy binary .doc via available system tools."""
    for tool in ("antiword", "catdoc"):
        exe = shutil.which(tool)
        if exe is None:
            continue
        try:
            proc = subprocess.run(
                [exe, str(path)],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if proc.returncode == 0:
            text = proc.stdout.decode("utf-8", errors="replace").strip()
            if text:
                return text
    return None


def _extract_rtf(path: Path) -> str | None:
    """Extract text from .rtf using the platform textutil (macOS) if available."""
    exe = shutil.which("textutil")
    if exe is None:
        return None
    try:
        proc = subprocess.run(
            [exe, "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode == 0:
        return proc.stdout.decode("utf-8", errors="replace").strip()
    return None


def _office_text(path: Path, suffix: str) -> str | None:
    """Return extracted text for an office document, or None if unsupported."""
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".doc":
        return _extract_doc(path)
    if suffix == ".rtf":
        return _extract_rtf(path)
    return None


class LocalFsBackend:
    def __init__(self, policy: FsPolicy, host: str) -> None:
        self._policy = policy
        self._host = host

    def _resolve(self, path: str) -> Path:
        return self._policy.resolve(self._host, path)

    def list_dir(
        self,
        path: str,
        *,
        recursive: bool = False,
        max_entries: int = 1000,
    ) -> dict[str, object]:
        resolved = self._resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(path)
        if not resolved.is_dir():
            raise NotADirectoryError(path)

        entries: list[dict[str, object]] = []
        iterator = resolved.rglob("*") if recursive else resolved.iterdir()
        for child in sorted(iterator, key=lambda p: str(p).lower()):
            if recursive and child == resolved:
                continue
            entries.append(_stat_entry(child))
            if len(entries) >= max_entries:
                break

        return {
            "host": self._host,
            "path": str(resolved),
            "entries": entries,
            "truncated": len(entries) >= max_entries,
        }

    def read(
        self,
        path: str,
        *,
        offset: int = 0,
        max_bytes: int = 2_097_152,
    ) -> dict[str, object]:
        resolved = self._resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(path)
        if not resolved.is_file():
            raise IsADirectoryError(path)

        size = resolved.stat().st_size
        if offset < 0:
            raise ValueError("offset must be >= 0")

        with open(resolved, "rb") as f:
            if offset:
                f.seek(offset)
            data = f.read(max_bytes + 1)

        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]

        classic_content: str
        try:
            classic_content = data.decode("utf-8")
            encoding = "utf-8"
            office_text = None
        except UnicodeDecodeError:
            encoding = "base64"
            classic_content = base64.b64encode(data).decode("ascii")
            office_text = None
            suffix = resolved.suffix.lower()
            if offset == 0 and suffix in _OFFICE_SUFFIXES:
                office_text = _office_text(resolved, suffix)

        content = office_text if office_text is not None else classic_content
        if office_text is not None:
            encoding = "extracted"

        mime, _ = mimetypes.guess_type(str(resolved))
        return {
            "host": self._host,
            "path": str(resolved),
            "size": size,
            "offset": offset,
            "bytes_read": len(data),
            "truncated": truncated or (offset + len(data) < size),
            "encoding": encoding,
            "content_type": mime or "application/octet-stream",
            "content": content,
        }

    def stat(self, path: str) -> dict[str, object]:
        resolved = self._resolve(path)
        if not resolved.exists():
            return {"host": self._host, "path": str(resolved), "exists": False}
        entry = _stat_entry(resolved)
        entry["host"] = self._host
        entry["exists"] = True
        return entry

    def exists(self, path: str) -> dict[str, object]:
        try:
            resolved = self._resolve(path)
        except FsAccessDenied:
            raise
        return {
            "host": self._host,
            "path": path,
            "exists": resolved.exists(),
            "resolved": str(resolved),
        }

    def glob(self, pattern: str, *, max_results: int = 200) -> dict[str, object]:
        if not pattern.strip():
            raise ValueError("pattern is required")

        host_policy = self._policy.hosts[self._host]
        matches: list[dict[str, object]] = []

        for root in host_policy.roots:
            root_path = root.expanduser().resolve()
            if not root_path.exists():
                continue
            for hit in root_path.glob(pattern):
                try:
                    resolved = self._policy.resolve(self._host, str(hit))
                except FsAccessDenied:
                    continue
                if not resolved.exists():
                    continue
                matches.append(_stat_entry(resolved))
                if len(matches) >= max_results:
                    return {
                        "host": self._host,
                        "pattern": pattern,
                        "matches": matches,
                        "truncated": True,
                    }

        return {
            "host": self._host,
            "pattern": pattern,
            "matches": matches,
            "truncated": False,
        }
