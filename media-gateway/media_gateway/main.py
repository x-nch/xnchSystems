"""FastAPI app factory + uvicorn entry point.

Runs as `python -m media_gateway.main` (see media-gateway.service). Bind
address/port come from env so the unit stays static and the operator picks
the private interface at deploy time.
"""
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from contextlib import asynccontextmanager

from .config import Settings
from .executors import Dispatcher
from .langfuse import get_client
from .models import HealthResponse
from .queue import Executor, MediaQueue
from .routes import router
from .store import JobStore
from .tasks import stub_executor

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    executor: Executor | None = None,
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.inbox_dir.mkdir(parents=True, exist_ok=True)
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)

        store = JobStore()
        langfuse = get_client(settings)
        runner: Executor = executor or Dispatcher(settings, langfuse=langfuse)
        queue = MediaQueue(store=store, executor=runner, langfuse=langfuse)
        queue.start()

        app.state.settings = settings
        app.state.store = store
        app.state.queue = queue
        app.state.langfuse = langfuse
        logger.info(
            "media-gateway up: inbox=%s outbox=%s worker=%s",
            settings.inbox_dir,
            settings.outbox_dir,
            queue.running,
        )
        try:
            yield
        finally:
            await queue.stop()
            if hasattr(runner, "aclose"):
                await runner.aclose()
            await langfuse.aclose()

    app = FastAPI(
        title="Media Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = Settings()
    uvicorn.run(app, host=settings.bind_host, port=settings.port)
