"""Secret denylist patterns and Luhn validation for card-shaped numbers."""
import re

from xnch_train.scrub.patterns import (
    CARD_CANDIDATE,
    PATTERN_SET_VERSION,
    SECRET_RULES,
    find_secret_spans,
    luhn_valid,
)


def test_pattern_set_version_is_pinned() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}\.\d+", PATTERN_SET_VERSION)


def test_luhn_accepts_and_rejects() -> None:
    assert luhn_valid("4532015112830366")      # valid Visa-shaped test number
    assert not luhn_valid("4532015112830367")  # same digits, fails checksum
    assert not luhn_valid("")                  # empty never validates


def test_api_keys_detected() -> None:
    text = "use sk-proj-abcd1234EFGH5678ijkl today"
    spans = [s for s in find_secret_spans(text) if s[0] == "api_key"]
    assert len(spans) == 1
    start, end = spans[0][1], spans[0][2]
    assert text[start:end].startswith("sk-proj-")


def test_bearer_token_detected() -> None:
    spans = [s for s in find_secret_spans("Authorization: Bearer abc.def.ghi")
             if s[0] == "bearer_token"]
    assert len(spans) == 1


def test_password_kv_detected() -> None:
    spans = [s for s in find_secret_spans('{"password": "hunter2"}')
             if s[0] == "password_kv"]
    assert len(spans) == 1


def test_card_only_when_luhn_valid() -> None:
    good = "4532 0151 1283 0366"   # Luhn-valid, spaced
    bad = "4532 0151 1283 0367"    # fails checksum
    good_spans = [s for s in find_secret_spans(f"card {good} ok") if s[0] == "card_number"]
    bad_spans = [s for s in find_secret_spans(f"ref {bad} x") if s[0] == "card_number"]
    assert len(good_spans) == 1
    assert bad_spans == []


def test_card_candidate_regex_shape() -> None:
    m = CARD_CANDIDATE.search("pay 4532015112830366 now")
    assert m is not None
