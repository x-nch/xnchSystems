"""QLoRA SFT trainer subpackage for Ornith customization (Phase 1)."""
from .goal import GoalClient, claim_goal, emit_promotion_proposal
from .merge import merge_and_requant
from .qlora import SftResult, run_sft
from .registry import CheckpointID, CheckpointRegistry

__all__ = [
    "SftResult",
    "run_sft",
    "merge_and_requant",
    "CheckpointRegistry",
    "CheckpointID",
    "GoalClient",
    "claim_goal",
    "emit_promotion_proposal",
]
