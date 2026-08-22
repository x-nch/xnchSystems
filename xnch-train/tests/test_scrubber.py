# xnch-train/tests/test_scrubber.py
"""Scrubber applies denylist + pseudonymization, tracks per-rule counts."""
from datetime import UTC, datetime

from xnch_train.models.records import RecordSource, ScrubStatus, TrainingRecord
from xnch_train.scrub.scrubber import Scrubber

KEY = b"unit-secret"


def _make_record(input_context: str = "", output: str = "") -> TrainingRecord:
    return TrainingRecord(
        trace_id="tr-1",
        ts=datetime(2026, 8, 1, tzinfo=UTC),
        source=RecordSource.TRACE,
        input_context=input_context,
        output=output,
    )


def _make_scrubber() -> Scrubber:
    return Scrubber(KEY)


def test_scrub_returns_new_record_marked_scrubbed() -> None:
    original = _make_record(output="call sk-proj-abcd1234EFGH5678ijk now")
    scrubbed = _make_scrubber().scrub(original)
    assert scrubbed is not original
    assert scrubbed.scrub_status is ScrubStatus.SCRUBBED
    assert "sk-proj-" not in scrubbed.output
    assert original.scrub_status is ScrubStatus.RAW  # input untouched


def test_luhn_invalid_number_survives() -> None:
    scrubbed = _make_scrubber().scrub(_make_record(output="ref 4532015112830367"))
    assert "4532015112830367" in scrubbed.output


def test_luhn_valid_card_redacted() -> None:
    scrubbed = _make_scrubber().scrub(_make_record(output="card 4532015112830366"))
    assert "4532015112830366" not in scrubbed.output
    assert "[REDACTED:card_number]" in scrubbed.output


def test_secrets_redacted_with_rule_tag() -> None:
    scrubbed = _make_scrubber().scrub(
        _make_record(output='Authorization: Bearer tok1234567890abcdef')
    )
    assert "[REDACTED:bearer_token]" in scrubbed.output


def test_pseudonymization_applies_to_both_fields() -> None:
    scrubbed = _make_scrubber().scrub(
        _make_record(input_context="user alice@example.com",
                     output="acct 7001002003 charged")
    )
    assert "alice@example.com" not in scrubbed.input_context
    assert "7001002003" not in scrubbed.output
    assert "@pseudo.local" in scrubbed.input_context


def test_scrub_many_counts_rules() -> None:
    records = [
        _make_record(output="k sk-proj-abcd1234EFGH5678ijk"),
        _make_record(input_context="mail bob@example.com"),
    ]
    scrubbed, counts = _make_scrubber().scrub_many(records)
    assert len(scrubbed) == 2
    assert all(r.scrub_status is ScrubStatus.SCRUBBED for r in scrubbed)
    assert counts.get("api_key") == 1
    assert counts.get("email") == 1


def test_two_secrets_in_one_field_both_redacted() -> None:
    scrubbed = _make_scrubber().scrub(_make_record(
        output="AAAA sk-proj-abcd1234EFGH5678ijk Bearer tok1234567890abcdef"))
    assert "sk-proj-" not in scrubbed.output
    assert "tok123456" not in scrubbed.output
    assert "[REDACTED:api_key]" in scrubbed.output
    assert "[REDACTED:bearer_token]" in scrubbed.output


def test_bearer_wrapped_luhn_card_single_region() -> None:
    scrubbed = _make_scrubber().scrub(_make_record(
        output="Authorization: Bearer 4532015112830366"))
    assert "4532015112830366" not in scrubbed.output
    assert "[REDACT[" not in scrubbed.output


def test_digit_run_counted_for_word_adjacent_runs() -> None:
    records = [_make_record(input_context="id_9999999 ok")]
    _, counts = _make_scrubber().scrub_many(records)
    assert counts.get("digit_run") == 1
