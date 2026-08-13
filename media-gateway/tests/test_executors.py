"""Executor tests: ComfyUI dispatch + Qwen-VL understanding via httpx MockTransport."""
import json
from pathlib import Path

import httpx
import pytest

from media_gateway.config import Settings
from media_gateway.executors import ComfyExecutor, QwenVlExecutor
from media_gateway.models import FileKind, MediaJob

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / "workflows"


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        token="t",
        inbox_dir=tmp_path / "inbox",
        outbox_dir=tmp_path / "outbox",
        comfy_input_dir=tmp_path / "comfy_input",
        comfy_output_dir=tmp_path / "comfy_output",
        workflows_dir=WORKFLOWS_DIR,
        litellm_url="http://litellm.test/v1",
        litellm_key="proxy-key",
    )


def _content_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".mp4": "video/mp4",
    }.get(ext, "application/octet-stream")


def _make_job(task: str, input_paths: list[Path]) -> MediaJob:
    records = [
        {
            "file_id": f"f{i}",
            "filename": path.name,
            "path": str(path),
            "content_type": _content_type(path.name),
            "size_bytes": path.stat().st_size,
            "kind": FileKind.INBOX,
        }
        for i, path in enumerate(input_paths)
    ]
    return MediaJob(task=task, prompt="a teal cube", input_files=records)


class TestComfyExecutor:
    @pytest.mark.asyncio
    async def test_substitutes_and_collects_outputs(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.inbox_dir.mkdir()
        settings.comfy_input_dir.mkdir()
        settings.comfy_output_dir.mkdir()
        (settings.inbox_dir / "in.png").write_bytes(b"\x89PNG\x00")

        (settings.comfy_output_dir / "out_00001_.png").write_bytes(b"\x89PNG\x00")

        seen = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/prompt":
                payload = json.loads(request.content)
                wf = payload["prompt"]
                sampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
                loader = next(n for n in wf.values() if n["class_type"] == "LoadImage")
                assert wf["4"]["inputs"]["text"] == "a teal cube"
                assert isinstance(sampler["inputs"]["seed"], int)
                assert loader["inputs"]["image"].endswith("in.png")
                seen["copied"] = loader["inputs"]["image"]
                return httpx.Response(200, json={"prompt_id": "p1"})
            if request.url.path == "/history/p1":
                return httpx.Response(
                    200,
                    json={
                        "p1": {
                            "status": {"status_str": "success"},
                            "outputs": {
                                "9": {
                                    "images": [
                                        {"filename": "out_00001_.png", "subfolder": "", "type": "output"}
                                    ]
                                }
                            },
                        }
                    },
                )
            return httpx.Response(404)

        job = _make_job("edit_image", [settings.inbox_dir / "in.png"])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=settings.comfy_url)
        executor = ComfyExecutor(settings, client=client)
        records = await executor(job)
        await executor.aclose()

        assert len(records) == 1
        assert records[0].kind == FileKind.OUTBOX
        assert records[0].content_type == "image/png"
        assert Path(records[0].path).is_file()
        assert Path(records[0].path).read_bytes() == b"\x89PNG\x00"
        assert seen["copied"]
        assert (settings.comfy_input_dir / seen["copied"]).is_file()

    @pytest.mark.asyncio
    async def test_copies_video_to_input_root(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.inbox_dir.mkdir()
        settings.comfy_output_dir.mkdir()
        (settings.inbox_dir / "clip.mp4").write_bytes(b"fakemp4")
        (settings.comfy_output_dir / "clip_out.mp4").write_bytes(b"outmp4")
        copied = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/prompt":
                payload = json.loads(request.content)
                copied["name"] = payload["prompt"]["6"]["inputs"]["file"]
                assert copied["name"].startswith("video/") is False
                return httpx.Response(200, json={"prompt_id": "p2"})
            if request.url.path == "/history/p2":
                return httpx.Response(
                    200,
                    json={
                        "p2": {
                            "status": {"status_str": "success"},
                            "outputs": {"14": {"videos": [{"filename": "clip_out.mp4", "subfolder": "", "type": "output"}]}},
                        }
                    },
                )
            return httpx.Response(404)

        job = _make_job("video_to_video", [settings.inbox_dir / "clip.mp4"])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=settings.comfy_url)
        executor = ComfyExecutor(settings, client=client)
        records = await executor(job)
        await executor.aclose()

        assert (settings.comfy_input_dir / copied["name"]).is_file()
        assert len(records) == 1
        assert records[0].content_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_failed_history_raises(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.inbox_dir.mkdir()
        (settings.inbox_dir / "in.png").write_bytes(b"\x89PNG\x00")

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/prompt":
                return httpx.Response(200, json={"prompt_id": "p3"})
            if request.url.path == "/history/p3":
                return httpx.Response(
                    200,
                    json={
                        "p3": {
                            "status": {
                                "status_str": "error",
                                "messages": [
                                    ["execution_start", {}],
                                    ["execution_error", {"exception_type": "torch.OutOfMemoryError", "exception_message": "Allocation on device 0 would exceed allowed memory."}],
                                ],
                            },
                            "outputs": {},
                        }
                    },
                )
            return httpx.Response(404)

        job = _make_job("edit_image", [settings.inbox_dir / "in.png"])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=settings.comfy_url)
        executor = ComfyExecutor(settings, client=client)
        with pytest.raises(RuntimeError) as exc:
            await executor(job)
        await executor.aclose()

        assert "torch.OutOfMemoryError" in str(exc.value)
        assert "exceed allowed memory" in str(exc.value)


class TestQwenVlExecutor:
    @pytest.mark.asyncio
    async def test_calls_litellm_and_sets_result_text(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.inbox_dir.mkdir()
        (settings.inbox_dir / "img.png").write_bytes(b"\x89PNG\x00")

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer proxy-key"
            body = json.loads(request.content)
            assert body["model"] == "qwen-vl"
            content = body["messages"][0]["content"]
            assert content[0]["type"] == "text"
            assert content[1]["type"] == "image_url"
            assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "A teal image"}}],
                    "usage": {"total_tokens": 12},
                },
            )

        job = _make_job("understand", [settings.inbox_dir / "img.png"])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=settings.litellm_url)
        executor = QwenVlExecutor(settings, client=client)
        records = await executor(job)
        await executor.aclose()

        assert records == []
        assert job.result_text == "A teal image"

    @pytest.mark.asyncio
    async def test_raises_on_upstream_error(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.inbox_dir.mkdir()
        (settings.inbox_dir / "img.png").write_bytes(b"\x89PNG\x00")

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "boom"})

        job = _make_job("understand", [settings.inbox_dir / "img.png"])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=settings.litellm_url)
        executor = QwenVlExecutor(settings, client=client)
        with pytest.raises(httpx.HTTPStatusError):
            await executor(job)
        await executor.aclose()
