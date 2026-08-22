# xnch_train/scrub/pseudonymize.py
"""Entity pseudonymization — HMAC-with-local-key, format-preserving.

Same input + same key ⇒ same tag, so entity identity relationships survive
training while the raw value never appears in a dataset (ADR §1).

Apply exactly once: re-application corrupts emitted tokens (idempotency
contract).
"""
import hmac
import re

_TOKENIZER: re.Pattern[str] = re.compile(
    r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"|(?P<digits>(?<!\d)\d{7,}(?!\d))"
)

_TAG_LEN = 16


class EntityPseudonymizer:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def tag(self, value: str) -> str:
        """Deterministic hex tag for one entity value."""
        digest = hmac.new(self._key, value.encode("utf-8"), "sha256").hexdigest()
        return digest[:_TAG_LEN]

    def pseudonymize(self, text: str) -> str:
        """Replace emails and long digit runs with stable pseudo-tokens.

        Single pass: emitted tokens are never rescanned.
        """

        def _replace(match: re.Match[str]) -> str:
            if match.lastgroup == "email":
                return f"<id:{self.tag(match.group('email'))}>@pseudo.local"
            run = match.group("digits")
            return f"<num:{self.tag(run)}:{len(run)}>"

        return _TOKENIZER.sub(_replace, text)
