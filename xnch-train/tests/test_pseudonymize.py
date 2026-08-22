# xnch-train/tests/test_pseudonymize.py
"""Deterministic, format-preserving entity pseudonymization."""
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


def test_no_raw_email_or_account_leaks() -> None:
    out = _make_pseudo().pseudonymize(
        "acct 7001002003 owner bob@corp.example paid"
    )
    assert "bob@corp.example" not in out
    assert "7001002003" not in out
