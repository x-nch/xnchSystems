"""Secret-pattern denylist — first scrub layer before anything leaves memory.

Version-stamped: bump PATTERN_SET_VERSION whenever rules change so scrub
manifests stay auditable (ADR §1 hygiene requirements).
"""
import re

PATTERN_SET_VERSION = "2026-08.1"

SECRET_RULES: dict[str, re.Pattern[str]] = {
    # OpenAI-style, GitHub tokens, generic high-entropy key assignments
    "api_key": re.compile(
        r"(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"
    ),
    "bearer_token": re.compile(
        r"(?i:bearer\s+[A-Za-z0-9._~+/=-]{8,})"
    ),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "password_kv": re.compile(
        r"(?i)(?:\"?(?:password|passwd|secret|api[_-]?token)\"?\s*[:=]\s*)"
        r"(\"[^\"]{4,}\"|'[^']{4,}'|[^\s,\"']{4,})"
    ),
}

# Card-shaped runs: 13–19 digits with optional spaces/dashes between groups.
CARD_CANDIDATE: re.Pattern[str] = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_valid(number: str) -> bool:
    """Standard Luhn checksum over stripped digits; False when too short."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = (len(digits) - 2) % 2
    for i, d in enumerate(digits[:-1]):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return (checksum + digits[-1]) % 10 == 0


def find_secret_spans(text: str) -> list[tuple[str, int, int]]:
    """All redaction spans as (rule_name, start, end); non-overlapping per rule.

    Card candidates are reported only when they pass the Luhn check —
    random long numbers (order IDs etc.) must survive untouched.
    """
    spans: list[tuple[str, int, int]] = []
    for name, pattern in SECRET_RULES.items():
        spans.extend((name, m.start(), m.end()) for m in pattern.finditer(text))
    for m in CARD_CANDIDATE.finditer(text):
        if luhn_valid(m.group(0)):
            spans.append(("card_number", m.start(), m.end()))
    spans.sort(key=lambda s: s[1])
    return spans
