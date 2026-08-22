"""xnch-train CLI — extract, validate-dataset, baseline (added in Task 12)."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from .config import XtrainSettings
from .extract.dataset_writer import write_dataset
from .extract.pg_extract import PgExtractor
from .models.manifest import build_scrub_manifest, validate_dataset
from .models.records import TrainingRecord
from .scrub.scrubber import Scrubber

app = typer.Typer(help="xnch-train Phase 0: data pipeline + eval harness")
logger = logging.getLogger(__name__)


@app.command("validate-dataset")
def validate_dataset_cmd(directory: Annotated[Path, typer.Argument()]) -> None:
    """Gate check: a dataset is usable only with a valid scrub manifest."""
    result = validate_dataset(directory)
    typer.echo(result.model_dump_json(indent=2))
    raise typer.Exit(code=0 if result.valid else 1)


@app.command("extract")
def extract_cmd(
    out: Annotated[Path, typer.Option(help="Output dataset directory")],
    pg_dsn: Annotated[Optional[str], typer.Option()] = None,
    skip_langfuse: Annotated[bool, typer.Option()] = False,
) -> None:
    """Extract → scrub → manifest → write. Nothing raw touches disk."""
    settings = XtrainSettings()
    records: list[TrainingRecord] = []

    async def _gather() -> list[TrainingRecord]:
        found: list[TrainingRecord] = []
        if pg_dsn is None:
            pg_dsn_effective = settings.postgres_url
        else:
            pg_dsn_effective = pg_dsn
        pg = PgExtractor(pg_dsn_effective)
        await pg.connect()
        try:
            found.extend(await pg.extract_outcomes())
            found.extend(await pg.extract_corrections())
        finally:
            await pg.close()
        if not skip_langfuse and settings.langfuse_host:
            from .extract.langfuse_extract import LangfuseExtractor

            lf = LangfuseExtractor(
                host=settings.langfuse_host,
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                page_size=settings.extract_page_size,
            )
            try:
                found.extend(await lf.extract_verdicts())
            finally:
                await lf.aclose()
        return found

    records = asyncio.run(_gather())
    scrubber = Scrubber(settings.pseudonymize_key())
    scrubbed, counts = scrubber.scrub_many(records)
    manifest = build_scrub_manifest(counts, settings.pseudonymize_secret)
    write_dataset(scrubbed, manifest, out)
    typer.echo(f"wrote {len(scrubbed)} scrubbed records to {out}; counts={counts}")


@app.command("baseline")
def baseline_cmd(
    base_url: Annotated[str, typer.Option()],
    model: Annotated[str, typer.Option()],
    suite: Annotated[Path, typer.Option()],
    out: Annotated[Path, typer.Option()],
    checkpoint_id: Annotated[str, typer.Option()] = "incumbent",
    fake_reply: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Capture an incumbent-only baseline report (five gate numbers)."""
    from .evalharness.client import FakeModelClient, VllmOpenAIClient
    from .evalharness.runner import run_baseline
    from .evalharness.suites import load_suite

    eval_suite = load_suite(suite)
    if fake_reply is not None:
        client: object = FakeModelClient([fake_reply])
    else:
        client = VllmOpenAIClient(base_url=base_url, model=model)

    async def _run() -> object:
        try:
            return await run_baseline(client, eval_suite, checkpoint_id=checkpoint_id)  # type: ignore[arg-type]
        finally:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()

    report = asyncio.run(_run())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")  # type: ignore[union-attr]
    typer.echo(f"wrote baseline report for {checkpoint_id} to {out}")


if __name__ == "__main__":
    app()
