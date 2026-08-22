# xnch_train/scrub/pseudonymize.py
"""Entity pseudonymization — HMAC-with-local-key, format-preserving.

Same input + same key ⇒ same tag, so entity identity relationships survive
training while the raw value never appears in a dataset (ADR §1).
"""
import hmac
import re

_EMAIL: re.Pattern[str] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LONG_DIGITS: re.Pattern[str] = re.compile(r"(?<![\w])\d{7,}(?![\w])")

_TAG_LEN = 16


class EntityPseudonymizer:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def tag(self, value: str) -> str:
        """Deterministic hex tag for one entity value."""
        digest = hmac.new(self._key, value.encode("utf-8"), "sha256").hexdigest()
        return digest[:_TAG_LEN]

    def pseudonymize(self, text: str) -> str:
        """Replace emails and long digit runs with stable pseudo-tokens."""
        text = _EMAIL.sub(lambda m: f"<id:{self.tag(m.group(0))}>@pseudo.local", text)
        text = _LONG_DIGITS.sub(
            lambda m: f"<num:{self.tag(m.group(0))}:{len(m.group(0))}>", text
        )
        return text
