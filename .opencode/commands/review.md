---
name: review
description: Run the review->fix->verify loop on the current diff or a named branch.
argument: optional branch or base ref (default: current diff vs HEAD~1)
---

# /review

Run the `review-loop` skill against {{argument}}.

1. `uvx code-review-graph update --repo .`
2. `code-review-graph.detect_changes` --base {{argument}}
3. Route HIGH-risk items to the `reviewer` agent.
4. Verify with `pytest`, re-detect, report.
