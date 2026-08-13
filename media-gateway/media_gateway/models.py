"""Pydantic models for media jobs and file records."""
import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class FileKind(StrEnum):
    INBOX = "inbox"
    OUTBOX = "outbox"


class FileRecord(BaseModel):
    file_id: str
    filename: str
    path: str
    content_type: str
    size_bytes: int
    kind: FileKind


class MediaJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str
    prompt: str = ""
    input_files: list[FileRecord] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    output_files: list[FileRecord] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int | None = None
    result_text: str | None = None

    def touch(self, status: JobStatus) -> None:
        self.status = status
        self.updated_at = time.time()

    @property
    def trace_id(self) -> str:
        return f"media-job-{self.job_id}"


class CreateJobRequest(BaseModel):
    task: str
    prompt: str = ""
    input_file_ids: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    engine: str
    enabled: bool
