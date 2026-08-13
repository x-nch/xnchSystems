"""media-gateway core tests: auth, upload validation, job lifecycle, health."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from media_gateway.config import Settings
from media_gateway.main import create_app
from media_gateway.models import JobStatus
from media_gateway.tasks import stub_executor


def _make_settings(tmp_path: Path, token: str = "test-token") -> Settings:
    return Settings(
        token=token,
        inbox_dir=tmp_path / "inbox",
        outbox_dir=tmp_path / "outbox",
        max_upload_mb=1,
    )


@pytest.fixture
def client(tmp_path):
    settings = _make_settings(tmp_path)
    app = create_app(settings=settings, executor=stub_executor)
    with TestClient(app) as c:
        yield c


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_health_is_open_and_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["engine"] == "media-gateway"
    assert body["enabled"] is True


def test_media_routes_require_token(client):
    resp = client.post("/media/jobs", json={"task": "generate_image"})
    assert resp.status_code == 401
    resp = client.post(
        "/media/jobs",
        json={"task": "generate_image"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401
    resp = client.get("/media/jobs")
    assert resp.status_code == 401


def test_token_missing_fails_closed(tmp_path):
    settings = _make_settings(tmp_path, token="")
    with TestClient(create_app(settings=settings)) as client:
        resp = client.get("/media/jobs")
        assert resp.status_code == 503


def test_upload_rejects_bad_extension(client):
    resp = client.post(
        "/media/files",
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_upload_rejects_mismatched_content_type(client):
    resp = client.post(
        "/media/files",
        files={"file": ("a.png", b"\x89PNG", "text/plain")},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_upload_rejects_oversized_file(client):
    resp = client.post(
        "/media/files",
        files={"file": ("big.png", b"\x89PNG" + b"\x00" * (1024 * 1024), "image/png")},
        headers=_auth(),
    )
    assert resp.status_code == 413


def test_upload_and_download_roundtrip(client):
    payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    up = client.post(
        "/media/files",
        files={"file": ("shot.png", payload, "image/png")},
        headers=_auth(),
    )
    assert up.status_code == 201
    record = up.json()
    assert record["kind"] == "inbox"
    assert record["size_bytes"] == len(payload)

    down = client.get(f"/media/files/{record['file_id']}", headers=_auth())
    assert down.status_code == 200
    assert down.content == payload


def test_job_lifecycle_through_stub_executor(client):
    job = client.post(
        "/media/jobs",
        json={"task": "generate_image", "prompt": "a cat"},
        headers=_auth(),
    )
    assert job.status_code == 201
    job_id = job.json()["job_id"]

    deadline = time.time() + 10
    final = None
    while time.time() < deadline:
        resp = client.get(f"/media/jobs/{job_id}", headers=_auth())
        assert resp.status_code == 200
        final = resp.json()
        if final["status"] in (JobStatus.DONE, JobStatus.FAILED):
            break
        time.sleep(0.1)

    assert final is not None
    assert final["status"] == JobStatus.DONE
    assert final["duration_ms"] is not None
    assert final["result_text"] is not None


def test_create_job_rejects_unknown_task(client):
    resp = client.post(
        "/media/jobs",
        json={"task": "definitely_not_a_task"},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_create_job_rejects_missing_input(client):
    resp = client.post(
        "/media/jobs",
        json={"task": "edit_image", "input_file_ids": ["nope"]},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_create_job_validates_input_count(client):
    resp = client.post(
        "/media/jobs",
        json={"task": "understand"},  # needs >=1 input
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_health_ok_when_worker_running(client):
    assert client.get("/health").json()["enabled"] is True
