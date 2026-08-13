"""HTTP surface: health, upload, jobs, file serving. All /media/* routes are
token-protected (bearer token from settings, fail-closed when unconfigured).
"""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from .config import ALLOWED_CONTENT_TYPES, Settings
from .models import CreateJobRequest, FileKind, FileRecord, HealthResponse, MediaJob
from .store import JobStore
from .tasks import get_task_spec, list_tasks

logger = logging.getLogger(__name__)

router = APIRouter()

_PASSTHROUGH_CONTENT_TYPES = {"application/octet-stream"}


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _store(request: Request) -> JobStore:
    return request.app.state.store


async def require_token(request: Request) -> None:
    settings = _settings(request)
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="gateway token not configured (MEDIA_GATEWAY_TOKEN)",
        )
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.token}"
    if auth != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
        )


def _validate_upload(settings: Settings, filename: str, content_type: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported extension '{ext}'; allowed: {settings.allowed_extensions}",
        )
    if (
        content_type not in _PASSTHROUGH_CONTENT_TYPES
        and content_type != ALLOWED_CONTENT_TYPES[ext]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"content-type '{content_type}' does not match extension '{ext}'",
        )
    return ext


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(request: Request) -> HealthResponse:
    queue = request.app.state.queue
    return HealthResponse(
        status="ok",
        engine="media-gateway",
        enabled=queue.running,
    )


@router.post("/media/files", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_token)])
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
) -> FileRecord:
    settings = _settings(request)
    store = _store(request)
    safe_name = Path(file.filename or "upload.bin").name
    ext = _validate_upload(settings, safe_name, file.content_type or "application/octet-stream")

    file_id = uuid.uuid4().hex
    dest = settings.inbox_dir / f"{file_id}.{ext}"

    written = 0
    try:
        with dest.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"file exceeds {settings.max_upload_mb}MB limit",
                    )
                handle.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    record = FileRecord(
        file_id=file_id,
        filename=safe_name,
        path=str(dest),
        content_type=file.content_type or ALLOWED_CONTENT_TYPES[ext],
        size_bytes=written,
        kind=FileKind.INBOX,
    )
    await store.put_file(record)
    logger.info("uploaded %s (%d bytes) -> %s", safe_name, written, dest)
    return record


@router.post("/media/jobs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_token)])
async def create_job(
    request: Request,
    payload: CreateJobRequest,
) -> MediaJob:
    store = _store(request)
    queue = request.app.state.queue

    spec = get_task_spec(payload.task)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown task '{payload.task}'; available: {[t.name for t in list_tasks()]}",
        )

    input_files: list[FileRecord] = []
    for file_id in payload.input_file_ids:
        record = await store.get_file(file_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"input file '{file_id}' not found",
            )
        input_files.append(record)

    if len(input_files) < spec.min_inputs or len(input_files) > spec.max_inputs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"task '{payload.task}' expects {spec.min_inputs}-{spec.max_inputs} input files, got {len(input_files)}",
        )

    job = MediaJob(
        task=payload.task,
        prompt=payload.prompt,
        input_files=input_files,
        options=payload.options,
    )
    await queue.submit(job)
    logger.info("job %s task=%s queued", job.job_id, job.task)
    return job


@router.get("/media/jobs/{job_id}", dependencies=[Depends(require_token)])
async def get_job(request: Request, job_id: str) -> MediaJob:
    job = await _store(request).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


@router.get("/media/jobs", dependencies=[Depends(require_token)])
async def list_jobs(request: Request, limit: int = 50) -> list[MediaJob]:
    return await _store(request).list_jobs(limit=min(limit, 200))


@router.get("/media/files/{file_id}", dependencies=[Depends(require_token)])
async def get_file(request: Request, file_id: str) -> FileResponse:
    record = await _store(request).get_file(file_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return FileResponse(record.path, media_type=record.content_type, filename=record.filename)
