"""In-memory job store.

Holds MediaJob records and a file index for inbox/outbox paths. Single-process,
asyncio.Lock-protected. Persistence is intentionally out of scope for v1 —
jobs are ephemeral and lost on restart.
"""
import asyncio
import logging

from .models import FileKind, FileRecord, JobStatus, MediaJob

logger = logging.getLogger(__name__)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, MediaJob] = {}
        self._files: dict[str, FileRecord] = {}
        self._lock = asyncio.Lock()

    async def put_file(self, record: FileRecord) -> None:
        async with self._lock:
            self._files[record.file_id] = record

    async def get_file(self, file_id: str) -> FileRecord | None:
        async with self._lock:
            return self._files.get(file_id)

    async def create_job(self, job: MediaJob) -> MediaJob:
        async with self._lock:
            self._jobs[job.job_id] = job
        return job

    async def get_job(self, job_id: str) -> MediaJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list_jobs(self, limit: int = 50) -> list[MediaJob]:
        async with self._lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True,
            )
            return jobs[:limit]

    async def update(self, job: MediaJob) -> MediaJob:
        async with self._lock:
            self._jobs[job.job_id] = job
        return job

    async def mark(self, job: MediaJob, status: JobStatus) -> None:
        job.touch(status)
        await self.update(job)
