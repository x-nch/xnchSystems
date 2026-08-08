"""Tests for CLI helper utilities."""

from cli.util import dedupe_memory_results, join_args, parse_recall_intent, parse_timer_line


def test_join_args_none_and_empty():
    assert join_args(None) is None
    assert join_args([]) is None
    assert join_args(["  "]) is None


def test_join_args_multi_word():
    assert join_args(["something", "or", "anything"]) == "something or anything"


def test_dedupe_memory_results_keeps_best_similarity():
    results = [
        {"content": "same text", "similarity": 0.2},
        {"content": "same text", "similarity": 0.9},
        {"content": "other", "similarity": 0.5},
    ]
    deduped = dedupe_memory_results(results)
    assert len(deduped) == 2
    assert deduped[0]["similarity"] == 0.9
    assert deduped[1]["content"] == "other"


def test_parse_recall_intent_matches_variants():
    assert parse_recall_intent("/recall nexi xnch") == "nexi xnch"
    assert parse_recall_intent("recall memory build something") == "build something"
    assert parse_recall_intent("memory recall foo bar") == "foo bar"
    assert parse_recall_intent("  /recall   spaced query  ") == "spaced query"


def test_parse_recall_intent_non_matches():
    assert parse_recall_intent("recall the time we met") is None
    assert parse_recall_intent("/recall") is None
    assert parse_recall_intent("") is None
    assert parse_recall_intent("plain message") is None


def test_parse_timer_line():
    line = (
        "Wed 2026-08-09 02:00:00 UTC  15h left  "
        "Sat 2026-08-08 02:00:20 UTC  23h ago  consolidation.timer  consolidation.service"
    )
    row = parse_timer_line(line)
    assert row is not None
    assert row["unit"] == "consolidation.timer"
    assert row["activates"] == "consolidation.service"
    assert row["next"].startswith("Wed")


def test_parse_timer_line_short_line():
    assert parse_timer_line("garbage") is None
