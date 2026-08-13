"""Job queue + GPU slot guard.

Single worker consumes the asyncio queue. The GPU slot is an asyncio.Semaphore
(1) so the guard survives future scaling to multiple workers: concurrent media
jobs are serialized against the one 3090 instead of OOMing it.
"""
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from .langfuse import LangfuseClient
from .models import FileRecord, JobStatus, MediaJob
from .store import JobStore

logger = logging.getLogger(__name__)

Executor = Callable[[MediaJob], Awaitable[list[FileRecord]]]


class MediaQueue:
    def __init__(
        self,
        store: JobStore,
        executor: Executor,
        langfuse: LangfuseClient | None = None,
    ) -> None:
        self._store = store
        self._executor = executor
        self._langfuse = langfuse
        self._queue: asyncio.Queue[MediaJob] = asyncio.Queue()
        self._slot = asyncio.Semaphore(1)
        self._worker: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._worker is not None and not self._worker.done()

    def start(self) -> None:
        if self.running:
            return
        self._worker = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
        self._worker = None

    async def submit(self, job: MediaJob) -> None:
        await self._store.create_job(job)
        await self._queue.put(job)

    async def _worker_loop(self) -> None:
        while True:
            job = await self._queue.get()
            async with self._slot:
                await self._run_job(job)
            self._queue.task_done()

    async def _run_job(self, job: MediaJob) -> None:
        started = time.time()
        job.started_at = started
        await self._store.mark(job, JobStatus.RUNNING)
        logger.info(
            "job %s task=%s running (gpu slot acquired)", job.job_id, job.task
        )
        try:
            outputs = await self._executor(job)
            for record in outputs:
                await self._store.put_file(record)
            job.output_files = outputs
            job.finished_at = time.time()
            job.duration_ms = int((job.finished_at - started) * 1000)
            await self._store.mark(job, JobStatus.DONE)
            logger.info(
                "job %s done in %sms outputs=%d",
                job.job_id,
                job.duration_ms,
                len(outputs),
            )
        except Exception as exc:
            job.error = str(exc)
            job.finished_at = time.time()
            job.duration_ms = int((job.finished_at - started) * 1000)
            await self._store.mark(job, JobStatus.FAILED)
            logger.exception("job %s failed: %s", job.job_id, exc)
        finally:
            if self._langfuse is not None:
                job.updated_at = time.time()
                try:
                    await self._langfuse.emit_job_span(job)
                except Exception:
                    logger.debug("langfuse emit failed", exc_info=True)
