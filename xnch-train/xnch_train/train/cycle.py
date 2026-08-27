"""Training cycle orchestrator for Ornith customization (Phase 1, Task 6).

Orders the Train → Merge → Register → Propose steps into a single
`xtrain-cycle@<run>` execution. Crash-safe: registration is the last
successful step, so a failure before it leaves no orphan checkpoint; the
rollback path only enforces registry quota hygiene.

All training/merge run with `fake=True` here (no torch, no GPU, no model
load). The real GPU-gated path is exercised in Step 6 (Node B window).
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
from pathlib import Path

from .goal import GoalClient, claim_goal, emit_promotion_proposal
from .merge import merge_and_requant
from .qlora import run_sft
from .registry import CheckpointRegistry

logger = logging.getLogger(__name__)

_XTRAIN_BASE_URL_ENV = "XTRAIN_XNCH_BASE_URL"
_DEFAULT_BASE_URL = "http://localhost:8080"


def run_cycle(
    client: GoalClient,
    *,
    base_model: str,
    dataset_dir: Path,
    out_dir: Path,
    goal_id: str | None = None,
    autonomous: bool = False,
) -> str | None:
    """Run one training cycle (Train → Merge → Register → Propose).

    Returns the new checkpoint id, or None when no Goal could be claimed (the
    cycle must fail safe and never take the GPU). All heavy steps use
    ``fake=True`` so this is hardware-free.
    """
    ckpt_id: str | None = None
    merged: Path | None = None
    try:
        if not autonomous:
            gid = claim_goal(
                client,
                objective="Phase 1 training cycle",
                max_steps=10,
                lease_owner="xtrain",
            )
            if not gid:
                logger.warning("no Goal claimed; aborting cycle (fail-safe)")
                return None

        sft = run_sft(
            base_model=base_model,
            dataset_dir=dataset_dir,
            out_dir=out_dir / "adapter",
            fake=True,
        )
        merged = merge_and_requant(
            adapter_dir=sft.adapter_dir,
            base_model=base_model,
            out_dir=out_dir / "merged",
            fake=True,
        )
        ckpt_id = f"ckpt-{datetime.date.today().isoformat()}-{goal_id or 'manual'}"

        reg = CheckpointRegistry(out_dir / "registry.sqlite")
        reg.register(ckpt_id, merged, datetime.date.today().isoformat())

        emit_promotion_proposal(
            client,
            {
                "type": "checkpoint.promotion",
                "checkpoint_id": ckpt_id,
                "goal_id": goal_id,
                "source": "xnch-train.cycle",
            },
        )
        return ckpt_id
    except Exception:
        logger.exception("cycle failed; leaving no orphan checkpoint")
        # Registration is the last successful step, so a failure here means
        # nothing was registered. Enforce quota hygiene and return None so the
        # systemd unit stays idle (Restart=no). Cleanup is best-effort.
        if ckpt_id is not None:
            try:
                reg = CheckpointRegistry(out_dir / "registry.sqlite")
                reg.retain()
            except Exception:
                pass
        return None


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: `python -m xnch_train.train.cycle %i`.

    The positional ``run_id`` comes from systemd ``%i``; it identifies this
    cycle run but does not change the orchestration order.
    """
    parser = argparse.ArgumentParser(description="Run one xnch-train cycle.")
    parser.add_argument("run_id", help="Cycle run id (systemd %%i).")
    parser.add_argument("--base", required=True, help="Base model name or path.")
    parser.add_argument("--dataset", type=Path, required=True, help="Scrubbed dataset dir.")
    parser.add_argument("--out", type=Path, required=True, help="Cycle output dir.")
    parser.add_argument("--goal-id", default=None, help="Explicit Goal id (optional).")
    parser.add_argument(
        "--autonomous", action="store_true", help="Skip Goal claim (manual mode)."
    )
    args = parser.parse_args(argv)

    client = GoalClient(
        base_url=os.environ.get(_XTRAIN_BASE_URL_ENV, _DEFAULT_BASE_URL)
    )
    result = run_cycle(
        client,
        base_model=args.base,
        dataset_dir=args.dataset,
        out_dir=args.out,
        goal_id=args.goal_id,
        autonomous=args.autonomous,
    )
    if result is None:
        print("no goal")
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
