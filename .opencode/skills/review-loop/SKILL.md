---
name: review-loop
description: Run the review->fix->verify loop on a diff or PR. Use after finishing a change set or before merge. Wires code-review-graph to subagents and pytest.
---

# review-loop

Closed-loop code review for this repo.

## Steps
1. **Refresh graph:** run `uvx code-review-graph update --repo .` (or rely on
   the post-commit hook).
2. **Detect:** `code-review-graph.detect_changes` (MCP tool) on the diff.
   Base = merge-base with `main` when reviewing a branch.
3. **Route:** for each HIGH-risk item, dispatch to the `devtools/code-reviewer`
   subagent (use the `reviewer` agent). For ML/AI code, also route to
   `ai/ml-engineer`. Pass the exact function/file + the risk note.
4. **Fix:** apply the suggested minimal change. Do not refactor unrelated code.
5. **Verify:** run `pytest nexi/tests xnch/tests tests` (and `pytest -k` for the
   touched area). All must pass.
6. **Re-detect:** run `detect_changes` again. If any HIGH-risk item remains,
   loop back to step 3 (max 3 iterations).
7. **Report:** summarize fixed items, remaining low-risk notes, and test result.

## Hard rules
- Never mark done without the pytest step passing.
- Never touch files outside the risk items' blast radius.
