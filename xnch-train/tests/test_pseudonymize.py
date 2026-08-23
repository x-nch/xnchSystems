# xnch-train/tests/test_pseudonymize.py
"""Deterministic, format-preserving entity pseudonymization."""
import re

from xnch_train.scrub.pseudonymize import EntityPseudonymizer

KEY = b"unit-secret"


def _make_pseudo() -> EntityPseudonymizer:
    return EntityPseudonymizer(KEY)


def test_tag_deterministic_and_hex() -> None:
    p = _make_pseudo()
    t1 = p.tag("alice@example.com")
    t2 = p.tag("alice@example.com")
    assert t1 == t2
    assert len(t1) == 16
    int(t1, 16)  # hex-parseable


def test_tag_depends_on_key() -> None:
    assert (EntityPseudonymizer(KEY).tag("x")
            != EntityPseudonymizer(b"other").tag("x"))


def test_email_replaced_format_preserved() -> None:
    out = _make_pseudo().pseudonymize("mail alice@example.com please")
    assert "alice@example.com" not in out
    assert "@pseudo.local" in out


def test_long_digit_runs_replaced_short_kept() -> None:
    p = _make_pseudo()
    out = p.pseudonymize("id 0042957831 qty 3 total 129")
    assert "0042957831" not in out
    assert "qty 3" in out          # short run kept
    assert "<num:" in out


def test_word_adjacent_digit_runs_replaced() -> None:
    out = _make_pseudo().pseudonymize("acct_7001002003 and ID=AB12345678 done")
    assert "7001002003" not in out
    assert "12345678" not in out
    assert "<num:" in out
    whole = _make_pseudo().pseudonymize("ref 12345678901 end")
    assert whole.count("<num:") == 1
    assert ":11>" in whole


def test_email_tags_never_corrupted_by_digit_pass() -> None:
    p = _make_pseudo()
    addresses = [f"user{i}@example.com" for i in range(60)]
    out = p.pseudonymize(" ".join(addresses))
    tokens = re.findall(r"<id:[0-9a-f]{16}>@pseudo\.local", out)
    assert len(tokens) == 60
    assert "<id:<" not in out
    ids = " ".join(re.findall(r"<id:[^>]*>", out))
    assert re.findall(r"<num:", ids) == []


def test_no_raw_email_or_account_leaks() -> None:
    out = _make_pseudo().pseudonymize(
        "acct 7001002003 owner bob@corp.example paid"
    )
    assert "bob@corp.example" not in out
    assert "7001002003" not in out
